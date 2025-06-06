import os
import subprocess
import logging
from config import VIDEO_EXTENSIONS
import sys
from filelock import FileLock
import time


class VideoDownloader:
    @staticmethod
    def download_video(output_dir, meta_info, progress_bar):
        progress_bar.set_description(f"Downloading")
        
        # 确保输出目录路径格式正确
        output_dir = os.path.normpath(output_dir)
        
        # 检查是否已经下载
        for ext in VIDEO_EXTENSIONS:
            video_filename = f"vid_{meta_info.video_id}{ext}"
            existing_video_path = os.path.normpath(os.path.join(output_dir, video_filename))
            if os.path.isfile(existing_video_path):
                logging.info(f'Video for ID {meta_info.video_id} already downloaded at {existing_video_path}')
                return existing_video_path

        # 创建锁文件路径
        lock_filename = f"vid_{meta_info.video_id}.lock"
        lock_file = os.path.normpath(os.path.join(output_dir, lock_filename))
        lock = FileLock(lock_file, timeout=600)  # 10分钟超时

        try:
            with lock:
                # 再次检查文件是否存在（可能在等待锁的过程中被其他线程下载完成）
                for ext in VIDEO_EXTENSIONS:
                    video_filename = f"vid_{meta_info.video_id}{ext}"
                    existing_video_path = os.path.normpath(os.path.join(output_dir, video_filename))
                    if os.path.isfile(existing_video_path):
                        logging.info(f'Video for ID {meta_info.video_id} was downloaded by another thread at {existing_video_path}')
                        return existing_video_path

                video_path = os.path.normpath(os.path.join(output_dir, f"vid_{meta_info.video_id}"))
                command = [
                    "yt-dlp",
                    "--cookies", 'D:/Downloads/youtube_cookies.txt', 
                    f"https://www.youtube.com/watch?v={meta_info.video_id}",
                    "--output", f"{video_path}.%(ext)s",
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--external-downloader", "aria2c",
                    "--external-downloader-args", "-x 16 -s 16 -k 1M --console-log-level=warn --quiet=true",
                    "--quiet",
                    "--concurrent-fragments", "16",
                    "--buffer-size", "32K",
                    "--http-chunk-size", "10M",
                    "--fragment-retries", "infinite"
                ]

                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

                output_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output.startswith("[download]"):
                        output_lines.append(output.strip())
                        sys.stdout.write("\033[F" * (len(output_lines) + 1))
                        sys.stdout.write("\033[J")
                        for line in output_lines:
                            print(line)
                        progress_bar.display()

                return_code = process.poll()
                if return_code == 0:
                    for ext in VIDEO_EXTENSIONS:
                        downloaded_file = os.path.normpath(video_path + ext)
                        if os.path.isfile(downloaded_file):
                            logging.info(f'Successfully downloaded video for ID {meta_info.video_id} to {downloaded_file}')
                            return downloaded_file
                else:
                    logging.error(f'Failed to download video for ID {meta_info.video_id}: Process ended with return code {return_code}')

                return None
                
        except TimeoutError:
            logging.error(f'Timeout waiting for lock on video ID {meta_info.video_id}')
            return None
        finally:
            # 如果下载失败或超时，确保删除锁文件
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass
