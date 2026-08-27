#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
admin="$root/admin"

if [ ! -f "$admin/Dockerfile" ]; then
  git clone --depth 1 https://github.com/beekle-team/laravel-react-docker-template.git "$admin"
  rm -rf "$admin/.git"
fi

cp -a "$root/admin-overlay/." "$admin/"

# php-fpm のサービス名をこのリポジトリの compose に合わせる
sed -i 's/fastcgi_pass app:9000;/fastcgi_pass admin-app:9000;/' "$admin/docker/nginx/default.conf"

echo "admin overlay applied"
