#!/bin/sh
for slug in chi www icse fse ndss usenix-security nsdi sigmod cvpr naacl asplos acl emnlp ubicomp; do
  count=$(grep -A50 "slug: ${slug}$" /app/data/*.yaml 2>/dev/null | grep -c "tracks:" || true)
  echo "${slug}: ${count} tracks entries"
done
