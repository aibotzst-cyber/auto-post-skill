<div align="center">

# 🤖 Auto Post Skill

**自动抓取 AI 大佬推文 → AI 翻译总结 → 发布到你的 X 账号**

[![Python 3.7+](https://img.shields.io/badge/Python-3.7+-green.svg)](https://www.python.org)
[![Built on x-tweet-fetcher](https://img.shields.io/badge/Built_on-x--tweet--fetcher-blue.svg)](https://github.com/ythx-101/x-tweet-fetcher)

*每日自动追踪 30 位 AI/科技 KOL · AI 提炼 Takeaway · Chrome CDP 自动发推*

</div>

---

## 🎯 它做什么？

```
每天自动执行：

1. 抓取 30 位 AI 大佬昨天的推文（零 API Key）
2. AI 翻译 + 总结成 Takeaway 要点
3. 通过 Chrome CDP 协议自动发布到 @YOUR_ACCOUNT
```

整个流程全自动，支持 cron 定时执行。

## 📐 架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  x-tweet-fetcher │     │   AI Summarizer   │     │  Chrome CDP     │
│  (抓取推文)       │ ──▶ │  (翻译+总结)       │ ──▶ │  (自动发推)      │
│                   │     │                    │     │                  │
│  · FxTwitter API  │     │  · Claude API      │     │  · WebSocket     │
│  · Camofox+Nitter │     │  · OpenAI API      │     │  · 模拟输入       │
│  · 零 API Key     │     │  · Ollama (本地)    │     │  · 自动点击发送   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## 🚀 快速开始

### 1. 安装

```bash
git clone https://github.com/aibotzst-cyber/auto-post-skill.git
cd auto-post-skill
```

无需 `pip install`，纯 Python 标准库。

### 2. 配置 AI 后端（三选一）

```bash
# 方案 A：Claude（推荐）
export ANTHROPIC_API_KEY="sk-ant-..."
export SUMMARIZER_BACKEND="claude"

# 方案 B：OpenAI / 兼容 API
export OPENAI_API_KEY="sk-..."
export SUMMARIZER_BACKEND="openai"
# export OPENAI_BASE_URL="https://your-proxy/v1"  # 可选，自定义端点

# 方案 C：本地 Ollama（零成本）
export SUMMARIZER_BACKEND="ollama"
export OLLAMA_MODEL="llama3"
# 需先安装 Ollama: https://ollama.ai
```

### 3. 启动 Chrome（用于发推）

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# 确保已登录你的 X 账号
```

### 4. 运行

```bash
# Dry Run — 只看结果，不发推
python3 auto_post.py --dry-run

# 指定用户
python3 auto_post.py --users karpathy,sama --dry-run

# 实际发推！
python3 auto_post.py --post

# 使用配置文件
python3 auto_post.py --config auto_post_config.json --post
```

## 👥 追踪的 KOL（30 位）

### AI 学术大佬
| 姓名 | 账号 | 身份 |
|------|------|------|
| Yann LeCun | @ylecun | Meta AI 首席科学家，图灵奖得主 |
| Geoffrey Hinton | @geoffreyhinton | AI 教父，图灵奖得主 |
| Andrew Ng | @AndrewYNg | 斯坦福教授，Coursera 联合创始人 |
| Andrej Karpathy | @karpathy | 前 Tesla AI 总监，前 OpenAI |
| Fei-Fei Li | @drfeifei | 斯坦福教授，ImageNet 创始人 |
| François Chollet | @fchollet | Keras 作者，Google |
| Ian Goodfellow | @goodfellow_ian | GAN 发明者 |
| Pieter Abbeel | @pabbeel | UC Berkeley 教授，Covariant CEO |
| Sebastian Raschka | @rasbt | ML 教育家，《Python ML》作者 |
| Christopher Olah | @ch402 | Anthropic 联合创始人 |

### AI 公司领袖
| 姓名 | 账号 | 身份 |
|------|------|------|
| Sam Altman | @sama | OpenAI CEO |
| Greg Brockman | @gdb | OpenAI 联合创始人 |
| Demis Hassabis | @demishassabis | Google DeepMind CEO，诺贝尔奖得主 |
| Dario Amodei | @darioamodei | Anthropic CEO |
| Elon Musk | @elonmusk | Tesla/xAI CEO |

### AI 内容与社区
| 姓名 | 账号 | 身份 |
|------|------|------|
| Lex Fridman | @lexfridman | AI 播客主持人 |
| Rowan Cheung | @rowancheung | The Rundown AI 创始人 |
| Ben Tossell | @bentossell | Ben's Bites 创始人 |
| Nathan Lambert | @natolambert | AI 研究员，RLHF 专家 |
| Yohei Nakajima | @yoheinakajima | BabyAGI 作者 |
| McKay Wrigley | @mckaywrigley | AI 开发者工具创始人 |
| Matt Shumer | @mattshumer_ | HyperWrite CEO |
| Riley Brown | @rileybrown_ai | AI 工程师 |
| Santiago Valdarrama | @svpino | ML 工程师，AI 教育者 |

### AI 研究与工程
| 姓名 | 账号 | 身份 |
|------|------|------|
| Jim Fan | @DrJimFan | NVIDIA 高级研究科学家 |
| Lilian Weng | @lilianweng | OpenAI 安全负责人 |
| Thomas Wolf | @Thom_Wolf | Hugging Face 联合创始人 |
| Jeff Dean | @JeffDean | Google 首席科学家 |

### AI 机构
| 名称 | 账号 | 简介 |
|------|------|------|
| Andreessen Horowitz | @a16z | 顶级 AI/科技 VC |
| Hugging Face | @huggingface | 开源 AI 社区 |

## ⚙️ 配置文件

`auto_post_config.json`:

```json
{
  "source_users": ["karpathy", "sama", "..."],
  "post_account": "YOUR_ACCOUNT",
  "chrome_cdp_port": 9222,
  "camofox_port": 9377,
  "fetch_limit": 50,
  "summary_lang": "zh-CN",
  "dry_run": true,
  "output_dir": "./output"
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `source_users` | 要抓取的用户列表 | 30 位 KOL |
| `post_account` | 发推目标账号 | YOUR_ACCOUNT |
| `chrome_cdp_port` | Chrome 调试端口 | 9222 |
| `camofox_port` | Camofox 端口 | 9377 |
| `fetch_limit` | 每用户最大抓取数 | 50 |
| `summary_lang` | 总结输出语言 | zh-CN |
| `dry_run` | 是否模拟运行 | true |
| `output_dir` | 结果保存目录 | ./output |

## ⏰ Cron 定时执行

```bash
# 每天早上 8 点自动执行（抓取昨天的推文 + 发推）
0 8 * * * cd /path/to/auto-post-skill && python3 auto_post.py --post >> logs/auto_post.log 2>&1

# 每天早上 8 点 Dry Run（仅生成总结，不发推）
0 8 * * * cd /path/to/auto-post-skill && python3 auto_post.py --dry-run >> logs/auto_post.log 2>&1
```

## 🔧 CLI 参数

```
python3 auto_post.py [OPTIONS]

选项：
  --config, -c FILE    配置文件路径
  --users, -u USERS    逗号分隔的用户名（覆盖配置文件）
  --dry-run, -n        模拟运行，不实际发推（默认）
  --post               实际发推
  --limit N            每用户最大抓取数（默认 50）
  --cdp-port PORT      Chrome CDP 端口（默认 9222）
  --camofox-port PORT  Camofox 端口（默认 9377）
  --output, -o DIR     输出目录（默认 ./output）
```

## 📂 项目结构

```
auto-post-skill/
├── auto_post.py           # 主流程编排（抓取→过滤→总结→发布）
├── auto_post_config.json  # 配置文件（用户列表、端口等）
├── cdp_poster.py          # Chrome CDP 发推模块
├── summarizer.py          # AI 翻译总结模块（Claude/OpenAI/Ollama）
├── SKILL.md               # Skill 定义
├── CHANGELOG.md           # 更新日志
├── VERSION                # 版本号
├── scripts/               # x-tweet-fetcher 核心（已集成）
│   ├── fetch_tweet.py     # 推文抓取（单条/时间线/评论/列表）
│   ├── camofox_client.py  # Camofox 浏览器客户端
│   ├── fetch_china.py     # 国内平台（微博/B站/CSDN/微信）
│   ├── sogou_wechat.py    # 搜狗微信搜索
│   ├── x_discover.py      # 关键词发现推文
│   ├── to_obsidian.py     # 导出到 Obsidian
│   ├── paper_to_obsidian.py  # 论文导出到 Obsidian
│   ├── tweet_growth_cli.py   # 推文增长追踪
│   ├── paper_recommend.py    # 论文推荐
│   ├── arxiv_author_finder.py # 作者查找
│   └── ...
└── output/                # 运行结果（git ignored）
```

## 🔌 依赖

| 组件 | 依赖 | 说明 |
|------|------|------|
| 推文抓取（基础） | Python 3.7+ | 零外部依赖 |
| 推文抓取（高级） | [Camofox](https://github.com/jo-inc/camofox-browser) | 评论/时间线/搜索 |
| AI 总结 | API Key（Claude/OpenAI）或 Ollama | 三选一 |
| 自动发推 | Chrome + `--remote-debugging-port` | 需登录目标账号 |

## 📝 工作流程详解

```
1. 抓取阶段
   ├── 遍历 30 位 KOL
   ├── 通过 FxTwitter API 获取时间线（零 Key）
   ├── 高级模式：Camofox + Nitter 翻页抓取
   └── 按日期过滤出「昨天」的推文

2. 总结阶段
   ├── 将每位用户的推文发送给 AI
   ├── AI 翻译成中文（如果是英文）
   ├── 提炼 Takeaway 关键要点
   └── 生成 ≤280 字符的总结推文

3. 发布阶段
   ├── 通过 Chrome CDP WebSocket 连接浏览器
   ├── 导航到 x.com/compose/post
   ├── 模拟输入推文内容
   └── 点击发送按钮
```

## 📄 License

[MIT](LICENSE) — 基于 [x-tweet-fetcher](https://github.com/ythx-101/x-tweet-fetcher) 构建

---

<div align="center">

*每天 5 分钟，掌握 AI 圈最新动态 🚀*

**发布到你配置的 X 账号**

</div>
