#!/usr/bin/env bash
set -euo pipefail
HELPDESK_PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HELPDESK_OCR_ROOT="$HELPDESK_PROJECT_ROOT/.runtime/tools/ocr"
mkdir -p "$HELPDESK_OCR_ROOT/debs" "$HELPDESK_OCR_ROOT/root"
cd "$HELPDESK_OCR_ROOT/debs"
apt-get download tesseract-ocr libtesseract5 liblept5 tesseract-ocr-eng tesseract-ocr-osd
for package in ./*.deb; do
  dpkg-deb -x "$package" "$HELPDESK_OCR_ROOT/root"
done
env LD_LIBRARY_PATH="$HELPDESK_OCR_ROOT/root/usr/lib/x86_64-linux-gnu" \
  "$HELPDESK_OCR_ROOT/root/usr/bin/tesseract" --version
