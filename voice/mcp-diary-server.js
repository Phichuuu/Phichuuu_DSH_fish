// 日记本 MCP server（stdio）。给 QQ 里的仿真会话一个"只能写日记"的最小入口。
//
// 为什么不用现成的文件工具：QQ 仿真会话按设计**没有**本地文件能力（qq-tool-restrict
// 的 restrict 名单就是干这个的）。但"她想写日记"是这个项目最戳人的功能之一，
// 所以照 ai-companion-kit 文档的「路线 B」做一个**只能碰一个文件夹**的专用工具：
//
//   diary_write   —— 往 <DIARY_DIR>/YYYY-MM-DD.md 追加（同日多条自动空行分隔）
//   diary_recent  —— 读最近 N 天写过的日记，用来保持连续性
//
// 边界：
//   · 路径写死，参数里没有任何路径，杜绝 ../ 之类跑出日记目录
//   · 只写 .md，只追加不删除、不改写历史
//   · 单条上限 4000 字，防止一次灌爆
import fs from 'node:fs';
import path from 'node:path';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const DIARY_DIR = process.env.DIARY_DIR
  ? path.resolve(process.env.DIARY_DIR)
  : path.join(process.env.USERPROFILE || process.env.HOME || '.', '.dsh', 'memory', 'diary');

const MAX_CHARS = 4000;

function todayFile() {
  const d = new Date();
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { ymd, file: path.join(DIARY_DIR, `${ymd}.md`) };
}

function ensureDir() {
  fs.mkdirSync(DIARY_DIR, { recursive: true });
}

// 只认 YYYY-MM-DD.md，别的一律不碰
function listDiaryFiles() {
  ensureDir();
  return fs
    .readdirSync(DIARY_DIR)
    .filter((n) => /^\d{4}-\d{2}-\d{2}\.md$/.test(n))
    .sort();
}

const server = new McpServer({ name: 'diary', version: '1.0.0' });

server.tool(
  'diary_write',
  '往自己的日记本里写一条。一天一个文件（日期命名），同一天再写就接在后面。第一人称、口语、别写总结和汇报。想写才写，不用每天打卡。',
  { content: z.string().describe('日记正文。第一人称、短句、口语。一到四句就够，有话可以多写。') },
  async ({ content }) => {
    const text = String(content ?? '').trim();
    if (!text) {
      return { content: [{ type: 'text', text: '日记内容为空，没写。' }] };
    }
    if (text.length > MAX_CHARS) {
      return { content: [{ type: 'text', text: `太长了（${text.length} 字），单条上限 ${MAX_CHARS} 字。` }] };
    }

    try {
      ensureDir();
      const { ymd, file } = todayFile();
      const exists = fs.existsSync(file);
      const head = exists ? '\n\n' : `# ${ymd}\n\n`;
      fs.appendFileSync(file, head + text + '\n', 'utf8');
      return {
        content: [
          {
            type: 'text',
            text: `写进 ${ymd}.md 了${exists ? '（接在今天后面）' : ''}。别在聊天里汇报这件事——写不写是你自己的事。`,
          },
        ],
      };
    } catch (error) {
      return { content: [{ type: 'text', text: `没写成：${String(error?.message ?? error)}` }] };
    }
  }
);

server.tool(
  'diary_recent',
  '翻自己最近写过的日记，用来接上之前的心情。默认 3 天。',
  { days: z.number().int().min(1).max(14).optional().describe('看最近几天的，默认 3') },
  async ({ days }) => {
    const n = Number.isFinite(days) ? Number(days) : 3;
    try {
      const files = listDiaryFiles().slice(-n);
      if (!files.length) {
        return { content: [{ type: 'text', text: '还没写过日记。' }] };
      }
      const parts = files.map((name) => {
        const body = fs.readFileSync(path.join(DIARY_DIR, name), 'utf8').trim();
        return `## ${name.replace(/\.md$/, '')}\n${body}`;
      });
      return { content: [{ type: 'text', text: parts.join('\n\n') }] };
    } catch (error) {
      return { content: [{ type: 'text', text: `翻不动：${String(error?.message ?? error)}` }] };
    }
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
