import os
import sys
import time
import threading
import webbrowser
import http.server
import traceback

BACKEND_PORT = 8000
FRONTEND_PORT = 8088


def open_browser():
    time.sleep(2)
    url = f"http://127.0.0.1:{FRONTEND_PORT}/index.html"
    print(f"[启动] 打开浏览器: {url}")
    webbrowser.open(url)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")
    frontend_dir = os.path.join(script_dir, "frontend")

    print("=" * 50)
    print("  企业销售全景数据大屏")
    print("=" * 50)
    print()
    print(f"[路径] 项目目录: {script_dir}")
    print(f"[路径] 后端目录: {backend_dir}")
    print(f"[路径] 前端目录: {frontend_dir}")

    if not os.path.isdir(backend_dir):
        print("ERROR: 未找到 backend 目录，请确认项目文件复制完整。")
        sys.exit(1)
    if not os.path.isfile(os.path.join(backend_dir, "app.py")):
        print("ERROR: 未找到 backend/app.py，请确认项目文件复制完整。")
        sys.exit(1)
    if not os.path.isfile(os.path.join(frontend_dir, "index.html")):
        print("ERROR: 未找到 frontend/index.html，请确认项目文件复制完整。")
        sys.exit(1)

    # 将 backend_dir 添加至 sys.path 并导入 app
    sys.path.insert(0, backend_dir)
    try:
        from app import app as fastapi_app
        from db import fetch_one
        import uvicorn
    except ImportError as e:
        print("ERROR: 导入后端服务失败。请确保 backend/requirements.txt 中的依赖已安装。")
        print(f"详细错误: {e}")
        sys.exit(1)
    except Exception as e:
        print("ERROR: 后端初始化失败。")
        print(f"详细错误: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        row = fetch_one("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name")
        print(f"[数据库] 连接成功: {row.get('database_name')} @ {row.get('server_name')}")
    except Exception as e:
        print("ERROR: 数据库连接失败。")
        print("请检查该电脑是否能访问 119.29.239.123，并确认 Python 已安装 pymssql。")
        print(f"详细错误: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 启动浏览器线程
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动后端线程
    def run_backend():
        try:
            uvicorn.run(
                fastapi_app,
                host="127.0.0.1",
                port=BACKEND_PORT,
                log_level="warning"
            )
        except Exception as e:
            print(f"[后端] 启动失败: {e}")
            traceback.print_exc()

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    print("[后端] FastAPI 服务已在后台线程启动...")

    # 启动前端线程
    class FrontendHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=frontend_dir, **kwargs)

        def log_message(self, format, *args):
            # 隐藏请求日志以避免控制台刷屏
            pass

        def handle_one_request(self):
            try:
                super().handle_one_request()
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                # Browser refresh/close can abort an in-flight static file response.
                # The service is still healthy, so keep the console clean.
                pass

    class ReusableHTTPServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True

        def handle_error(self, request, client_address):
            exc_type = sys.exc_info()[0]
            if exc_type in (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                return
            super().handle_error(request, client_address)

    def run_frontend():
        try:
            server = ReusableHTTPServer(("127.0.0.1", FRONTEND_PORT), FrontendHandler)
            server.serve_forever()
        except Exception as e:
            print(f"[前端] 静态服务启动失败: {e}")
            traceback.print_exc()

    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    frontend_thread.start()
    print("[前端] 静态文件服务已在后台线程启动...")

    print()
    print(f"  后端: http://127.0.0.1:{BACKEND_PORT}")
    print(f"  前端: http://127.0.0.1:{FRONTEND_PORT}/index.html")
    print()
    print("按 Ctrl+C 停止服务，或者直接关闭该窗口。所有绑定的端口会自动释放。")
    print("-" * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[停止] 关闭服务...")
        print("[完成] 所有服务已停止")


if __name__ == "__main__":
    main()
