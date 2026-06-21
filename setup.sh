#!/usr/bin/env bash
# Chubby Skills - 一键安装脚本
# 用法: bash setup.sh [skill-name ...]
#   不带参数 → 安装所有依赖
#   带参数   → 只安装指定 skill 的依赖
#
# 示例:
#   bash setup.sh                          # 全部安装
#   bash setup.sh douyin-transcribe        # 只装抖音转录
#   bash setup.sh podcast wechat           # 装播客 + 公众号

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }

ALL_SKILLS=(
    douyin-transcribe
    bilibili-transcribe
    tiktok-transcribe
    weibo-transcribe
    zhihu-transcribe
    youtube-transcribe
    podcast-transcribe
    wechat-article-ingest
    xiaohongshu-ingest
    x-ingest
    content-enrich
    knowledge-base-management
    industry-intelligence-radar
    learning-notes-automation
)

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        error "未找到 $1，请先安装"
        return 1
    fi
    info "已安装 $1"
}

# ── 解析参数 ──────────────────────────────────────────
INSTALL_ALL=true
SKILLS=()
if [[ $# -gt 0 ]]; then
    INSTALL_ALL=false
    for s in "$@"; do
        case "$s" in
            douyin|douyin-transcribe) SKILLS+=("douyin") ;;
            bilibili|bilibili-transcribe) SKILLS+=("bilibili") ;;
            tiktok|tiktok-transcribe) SKILLS+=("tiktok") ;;
            weibo|weibo-transcribe) SKILLS+=("weibo") ;;
            zhihu|zhihu-transcribe) SKILLS+=("zhihu") ;;
            youtube|youtube-transcribe) SKILLS+=("youtube") ;;
            podcast|podcast-transcribe) SKILLS+=("podcast") ;;
            wechat|wechat-article-ingest) SKILLS+=("wechat") ;;
            xiaohongshu|xhs|xiaohongshu-ingest) SKILLS+=("xiaohongshu") ;;
            x|twitter|x-ingest) SKILLS+=("x") ;;
            content|enrich|content-enrich) SKILLS+=("content") ;;
            knowledge|kb|knowledge-base-management) SKILLS+=("knowledge") ;;
            industry|radar|industry-intelligence-radar) SKILLS+=("industry") ;;
            learning|learning-notes-automation) SKILLS+=("learning") ;;
            *)
                error "未知 skill: $s" >&2
                echo "可用 skill:" >&2
                printf '  - %s\n' "${ALL_SKILLS[@]}" >&2
                exit 1
                ;;
        esac
    done
fi

needs() {
    # 检查是否需要安装某个 skill 的依赖
    if $INSTALL_ALL; then return 0; fi
    for s in "${SKILLS[@]}"; do
        if [[ "$1" == "$s" ]]; then return 0; fi
    done
    return 1
}

# ── 基础检查 ──────────────────────────────────────────
echo ""
echo "========================================="
echo "  Chubby Skills 安装助手"
echo "========================================="
echo ""

check_cmd python3
if needs "douyin" || needs "bilibili" || needs "tiktok" || needs "weibo" || needs "zhihu" || needs "youtube" || needs "xiaohongshu" || needs "x" || needs "podcast"; then
    check_cmd ffmpeg
fi
if needs "douyin" || needs "podcast" || needs "wechat"; then
    check_cmd curl
fi

# ── 视频转录依赖 (funasr + torch) ────────────────────
install_video_deps() {
    echo ""
    echo "--- 视频转录依赖 (funasr / torch) ---"
    if needs "douyin" || needs "bilibili" || needs "tiktok" || needs "weibo" || needs "zhihu" || needs "youtube" || needs "xiaohongshu" || needs "x" || needs "video"; then
        info "安装 funasr + torch（首次较慢，约 2-3 GB）..."
        pip install funasr modelscope torch torchaudio
        info "视频转录依赖安装完成"
    fi
}

# ── yt-dlp ────────────────────────────────────────────
install_ytdlp() {
    echo ""
    echo "--- yt-dlp ---"
    if needs "bilibili" || needs "tiktok" || needs "weibo" || needs "zhihu" || needs "youtube"; then
        if command -v yt-dlp &>/dev/null; then
            info "yt-dlp 已安装"
        else
            warn "未找到 yt-dlp，正在安装..."
            if [[ "$(uname)" == "Darwin" ]]; then
                brew install yt-dlp 2>/dev/null || pip install yt-dlp
            else
                pip install yt-dlp
            fi
            info "yt-dlp 安装完成"
        fi
    fi
}

# ── 播客转录依赖 (faster-whisper) ─────────────────────
install_podcast_deps() {
    echo ""
    echo "--- 播客转录依赖 (faster-whisper) ---"
    if needs "podcast"; then
        pip install faster-whisper
        info "播客转录依赖安装完成"
    fi
}

# ── 公众号处理依赖 ────────────────────────────────────
install_wechat_deps() {
    echo ""
    echo "--- 公众号处理依赖 ---"
    if needs "wechat"; then
        pip install beautifulsoup4 markitdown pymupdf
        info "公众号处理依赖安装完成"
    fi
}

# ── 翻译功能检查 ──────────────────────────────────────
check_translation() {
    if needs "youtube" || needs "learning"; then
        if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
            warn "翻译/闪卡功能需要 DEEPSEEK_API_KEY"
            warn "  export DEEPSEEK_API_KEY=your-key-here"
        else
            info "DEEPSEEK_API_KEY 已设置"
        fi
    fi
}

# ── 执行 ──────────────────────────────────────────────
install_video_deps
install_ytdlp
install_podcast_deps
install_wechat_deps
check_translation

echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""
echo "快速验证:"
echo "  python3 industry-intelligence-radar/scripts/scan.py --hours 1"
echo "  python3 podcast-transcribe/scripts/transcribe.py --help"
echo ""
