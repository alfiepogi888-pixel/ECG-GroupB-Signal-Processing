"""Scalable local ECG image preprocessing. Does NOT digitize ECG waveforms or diagnose."""
import argparse
import csv
import os
import sqlite3
import time
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter, UnidentifiedImageError

EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
Image.MAX_IMAGE_PIXELS = 300_000_000


def open_db(path):
    con = sqlite3.connect(path)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.execute('''CREATE TABLE IF NOT EXISTS results
      (relpath TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER,
       status TEXT NOT NULL, output TEXT, error TEXT, updated_at REAL)''')
    con.commit()
    return con


def scan(source):
    for root, dirs, files in os.walk(source):
        dirs.sort()
        files.sort()
        for file in files:
            p = Path(root) / file
            if p.suffix.lower() in EXTS:
                yield p


def filter_image(src, dst, mode, kernel):
    with Image.open(src) as opened:
        opened.load()
        im = ImageOps.exif_transpose(opened)
        if mode == 'grayscale':
            im = ImageOps.grayscale(im)
        else:
            im = im.convert('RGB')
        if kernel > 1:
            im = im.filter(ImageFilter.MedianFilter(size=kernel))
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.stem + '.partial' + dst.suffix)
        try:
            suffix = dst.suffix.lower()
            if suffix in ('.jpg', '.jpeg'):
                im.save(tmp, format='JPEG', quality=93, subsampling=0)
            elif suffix == '.png':
                im.save(tmp, format='PNG', compress_level=3)
            elif suffix in ('.tif', '.tiff'):
                im.save(tmp, format='TIFF', compression='tiff_deflate')
            elif suffix == '.bmp':
                im.save(tmp, format='BMP')
            else:
                im.save(tmp, format='WEBP', quality=93)
            os.replace(tmp, dst)
        finally:
            if tmp.exists():
                tmp.unlink()


def main():
    ap = argparse.ArgumentParser(description='Batch preprocess local ECG images with SQLite resume')
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--mode', choices=['color', 'grayscale'], default='color')
    ap.add_argument('--median', type=int, choices=[1, 3, 5], default=3,
                    help='Median kernel, 1 disables denoising')
    ap.add_argument('--limit', type=int, default=0, help='Limit processed candidates for a test; 0=all')
    ap.add_argument('--log-every', type=int, default=1000)
    ap.add_argument('--retry-errors', action='store_true')
    args = ap.parse_args()
    src = args.input.expanduser().resolve()
    out = args.output.expanduser().resolve()
    if not src.is_dir():
        ap.error(f'Input directory does not exist: {src}')
    if src == out or src in out.parents or out in src.parents:
        ap.error('Input and output directories must not contain one another')
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / 'manifest.sqlite3'
    con = open_db(db_path)
    total = done = skipped = failed = 0
    start = time.monotonic()
    try:
        for path in scan(src):
            if args.limit and total >= args.limit:
                break
            total += 1
            rel = path.relative_to(src)
            relkey = rel.as_posix()
            dest = out / 'processed' / rel
            try:
                st = path.stat()
                prior = con.execute('SELECT size,mtime_ns,status FROM results WHERE relpath=?', (relkey,)).fetchone()
                if prior and prior[0] == st.st_size and prior[1] == st.st_mtime_ns:
                    if prior[2] == 'ok' and dest.is_file() and dest.stat().st_size > 0:
                        skipped += 1
                        continue
                    if prior[2] == 'error' and not args.retry_errors:
                        skipped += 1
                        continue
                filter_image(path, dest, args.mode, args.median)
                con.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)',
                            (relkey, st.st_size, st.st_mtime_ns, 'ok', str(dest.relative_to(out)), None, time.time()))
                done += 1
            except (OSError, ValueError, UnidentifiedImageError) as exc:
                failed += 1
                st_size = st.st_size if 'st' in locals() else -1
                st_mtime = st.st_mtime_ns if 'st' in locals() else -1
                con.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)',
                            (relkey, st_size, st_mtime, 'error', None, str(exc)[:1000], time.time()))
                print(f'ERROR {relkey}: {exc}', flush=True)
            if total % 100 == 0:
                con.commit()
            if total % args.log_every == 0:
                con.commit()
                print(f'Scanned={total:,} new={done:,} skipped={skipped:,} errors={failed:,} '
                      f'elapsed={time.monotonic()-start:.0f}s', flush=True)
    except KeyboardInterrupt:
        print('Interrupted safely; rerun same command to resume.', flush=True)
    finally:
        con.commit()
        with (out / 'errors.csv').open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['relative_path', 'error'])
            writer.writerows(con.execute('SELECT relpath,error FROM results WHERE status="error" ORDER BY relpath'))
        con.close()
        print(f'Finished: visited={total:,}, new={done:,}, skipped={skipped:,}, errors={failed:,}')
        print('Processed images:', out / 'processed')
        print('State:', db_path)
        print('Errors:', out / 'errors.csv')


if __name__ == '__main__':
    main()
