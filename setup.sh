#!/usr/bin/env bash
# Chubby Skills - staged installer
#
# Usage:
#   bash setup.sh                 # light mode: zero/low-dependency tools
#   bash setup.sh light           # same as default
#   bash setup.sh video           # video transcription stack
#   bash setup.sh podcast         # podcast transcription stack
#   bash setup.sh wechat          # WeChat/PDF extraction stack
#   bash setup.sh all             # everything
#   bash setup.sh doctor          # environment check only
#   bash setup.sh bilibili xhs    # aliases are accepted

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }

has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

require_cmd() {
    if has_cmd "$1"; then
        info "已安装 $1"
    else
        error "未找到 $1：$2"
        return 1
    fi
}

run_doctor() {
    python3 tools/check_env.py
}

pip_install() {
    python3 -m pip install "$@"
}

install_ytdlp() {
    if has_cmd yt-dlp; then
        info "yt-dlp 已安装"
        return
    fi
    warn "未找到 yt-dlp，正在安装..."
    if [[ "$(uname)" == "Darwin" ]] && has_cmd brew; then
        brew install yt-dlp || pip_install yt-dlp
    else
        pip_install yt-dlp
    fi
}

install_light() {
    echo ""
    echo "--- light：零/轻依赖能力 ---"
    require_cmd python3 "请先安装 Python 3.9+"
    info "可直接使用：X 图文、小红书图文、情报雷达、知识库健康检查、content-enrich"
    warn "content-enrich / 学习笔记 / 爆款拆解需要按需设置 DEEPSEEK_API_KEY"
    warn "小红书采集建议按需设置 XHS_COOKIE"
}

install_video() {
    echo ""
    echo "--- video：视频转录依赖 ---"
    require_cmd python3 "请先安装 Python 3.9+"
    require_cmd ffmpeg "macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg"
    install_ytdlp
    warn "即将安装 funasr / modelscope / torch / torchaudio，首次安装体积较大。"
    pip_install funasr modelscope torch torchaudio
    info "视频转录依赖安装完成"
}

install_podcast() {
    echo ""
    echo "--- podcast：播客转录依赖 ---"
    require_cmd python3 "请先安装 Python 3.9+"
    require_cmd ffmpeg "macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg"
    pip_install faster-whisper
    info "播客转录依赖安装完成"
}

install_wechat() {
    echo ""
    echo "--- wechat：公众号/PDF 处理依赖 ---"
    require_cmd python3 "请先安装 Python 3.9+"
    pip_install beautifulsoup4 markitdown pymupdf
    info "公众号/PDF 处理依赖安装完成"
}

normalize_target() {
    case "$1" in
        light|x|twitter|xhs|xiaohongshu|content|radar|knowledge|kb)
            echo "light" ;;
        video|douyin|bilibili|youtube|tiktok|weibo|zhihu)
            echo "video" ;;
        podcast|rss)
            echo "podcast" ;;
        wechat|pdf|article)
            echo "wechat" ;;
        all)
            echo "all" ;;
        doctor|check)
            echo "doctor" ;;
        *)
            echo "unknown" ;;
    esac
}

echo ""
echo "========================================="
echo "  Chubby Skills 安装助手"
echo "========================================="

if [[ $# -eq 0 ]]; then
    set -- light
fi

want_light=false
want_video=false
want_podcast=false
want_wechat=false
want_all=false
want_doctor=false

for raw in "$@"; do
    target="$(normalize_target "$raw")"
    if [[ "$target" == "unknown" ]]; then
        error "未知安装目标：$raw"
        echo "可用目标：light / video / podcast / wechat / all / doctor"
        exit 2
    fi
    case "$target" in
        light) want_light=true ;;
        video) want_video=true ;;
        podcast) want_podcast=true ;;
        wechat) want_wechat=true ;;
        all) want_all=true ;;
        doctor) want_doctor=true ;;
    esac
done

if $want_doctor; then
    run_doctor
    exit 0
fi

if $want_all; then
    install_light
    install_video
    install_podcast
    install_wechat
else
    $want_light && install_light
    $want_video && install_video
    $want_podcast && install_podcast
    $want_wechat && install_wechat
fi

echo ""
echo "========================================="
echo "  安装步骤完成"
echo "========================================="
echo ""
echo "下一步建议："
echo "  python3 tools/check_env.py"
echo "  python3 tools/chubby.py quickstart"
echo "  python3 tools/platform_smoke.py --mode all --check"
echo "  python3 tools/golden_outputs.py examples/outputs"
