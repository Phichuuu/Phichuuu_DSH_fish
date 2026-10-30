// 语音 MCP：把"说一句话"变成一条真正的 QQ 语音条。
//
// 链路：本工具 -> 本地常驻服务（F:\RVC\voice-daemon.py, 127.0.0.1:8848）
//      -> edge-tts 生成中文语音 -> RVC 换成 tomori 音色 -> 写进 F:\qq-bridge\audio\
//      -> 返回文件名，agent 再用 qq_send_voice 把那条发出去。
//
// 为什么要两步（本工具只合成、不发送）：
//   发送走桥接自己的 qq_send_voice —— 白名单、限流、审计都在桥接里，
//   这里绕过它等于把风控交给一个 MCP 子进程，不值得。
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const DAEMON = process.env.VOICE_DAEMON_URL || 'http://127.0.0.1:8848'
const FEIYU = process.env.FEIYU_DAEMON_URL || 'http://127.0.0.1:8849';
const MIMO = process.env.MIMO_DAEMON_URL || 'http://127.0.0.1:8850';
const MINIMAX = process.env.MINIMAX_DAEMON_URL || 'http://127.0.0.1:8851';

const server = new McpServer({ name: 'voice', version: '1.0.0' });

server.tool(
  'voice_say',
  '把一段话合成成自己的声音（一条语音条），返回文件名。合成完还要调 qq_send_voice 把那个名字发出去，主人才听得到。适合短句（≤300 字）。语调语气都能自己调。',
  {
    text: z.string().describe('要说的话。口语、短句——这是语音，不是文章。'),
    mode: z
      .string()
      .optional()
      .describe('speak=说话（默认）；sing=唱歌（text 里直接写歌词）。'),
    emotion: z
      .string()
      .optional()
      .describe(
        '情绪：happy（开心）/ sad（难过）/ angry（生气）/ surprised（惊讶）/ fearful（害怕）/ disgusted（嫌弃）/ neutral（平静，想温柔就选这个）。不填就按默认。'
      ),
    style: z
      .string()
      .optional()
      .describe('用自然语言描述想要的味道，例如「懒懒的」「黏人」「小声嘀咕」。只在退回 MiMo 时生效。'),
    speed: z.number().optional().describe('语速 0.5~2.0，默认 1.05。困了慢一点、兴奋快一点。'),
    pitch: z.number().optional().describe('音调 -12~12，默认 2。越高越甜、越低越沉。'),
  },
  async ({ text, mode, style, pitch, emotion, speed }) => {
    let content = String(text ?? '').trim();
    if (!content) {
      return { content: [{ type: 'text', text: '没给内容。' }] };
    }

    const singing = String(mode || '').toLowerCase() === 'sing';
    if (singing && !content.startsWith('(唱歌)')) {
      content = '(唱歌)' + content;
    }

    // MiniMax 的 emotion 只认固定枚举；她写的是中文/自由描述时不要硬塞，
    // 否则接口会报错、整条链掉到备用引擎（2026-10-27 修）。
    const EMOTIONS = new Set(['happy', 'sad', 'angry', 'surprised', 'fearful', 'disgusted', 'neutral']);
    const EMOTION_ALIAS = {
      开心: 'happy', 高兴: 'happy', 快乐: 'happy',
      难过: 'sad', 伤心: 'sad', 委屈: 'sad',
      生气: 'angry', 不爽: 'angry', 炸毛: 'angry',
      惊讶: 'surprised', 吃惊: 'surprised',
      害怕: 'fearful', 怕: 'fearful',
      嫌弃: 'disgusted', 嫌: 'disgusted',
      平静: 'neutral', 温柔: 'neutral', 平常: 'neutral',
    };
    const rawEmotion = String(emotion || '').trim();
    let useEmotion = EMOTIONS.has(rawEmotion.toLowerCase()) ? rawEmotion.toLowerCase() : '';
    if (!useEmotion && rawEmotion) {
      for (const [k, v] of Object.entries(EMOTION_ALIAS)) {
        if (rawEmotion.includes(k)) { useEmotion = v; break; }
      }
    }

    const useSpeed = Number.isFinite(Number(speed)) && Number(speed) > 0 ? Number(speed) : 1.05;
    const usePitch = Number.isFinite(Number(pitch)) ? Number(pitch) : 2;

    // 回退链（2026-10-27 主人选定 MiniMax 少女音色）：
    //   说话：MiniMax(female-shaonv) -> MiMo 克隆 -> 本地 CosyVoice3 -> edge-tts+RVC
    //   唱歌：只有 MiMo 支持 (唱歌) 标签
    const minimaxBody = { text: content, voice: 'female-shaonv', speed: useSpeed, pitch: usePitch };
    if (useEmotion) minimaxBody.emotion = useEmotion;

    const engines = singing
      ? [
          { url: MIMO, body: { text: content, mode: 'preset', voice: '冰糖', style: style || '' }, label: 'MiMo 唱歌' },
        ]
      : [
          { url: MINIMAX, body: minimaxBody, label: 'MiniMax 少女音' },
          { url: MIMO, body: { text: content, mode: 'clone', style: style || '' }, label: 'MiMo 克隆' },
          { url: FEIYU, body: { text: content, style: 'cute' }, label: 'CosyVoice3' },
          { url: DAEMON, body: { text: content, pitch: usePitch ?? 0 }, label: 'edge-tts+RVC' },
        ];

    const failures = [];
    for (const engine of engines) {
      try {
        const res = await fetch(`${engine.url}/say`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify(engine.body),
          signal: AbortSignal.timeout(300000),
        });
        const data = await res.json();
        if (!data?.ok) {
          failures.push(`${engine.label}: ${data?.error ?? res.status}`);
          continue;
        }
        const via = data.model ? `，${data.model}` : '';
        return {
          content: [
            {
              type: 'text',
              text: `合成好了：${data.file}（${data.seconds} 秒${via}，用了 ${Math.round((data.took_ms || 0) / 1000)} 秒）。\n下一步调 qq_send_voice，voice 传 "${data.file}"。`,
            },
          ],
        };
      } catch (error) {
        failures.push(`${engine.label}: ${String(error?.message ?? error)}`);
      }
    }

    return {
      content: [
        {
          type: 'text',
          text: `两个语音引擎都没合成出来（${failures.join('；')}）。用文字说就行，别跟主人解释这个错误。`,
        },
      ],
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
