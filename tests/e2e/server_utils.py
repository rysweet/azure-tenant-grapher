def run_server(port, ready_conn):
    print("[E2E TEST CHILD] run_server entry")
    import uvicorn
    import requests
    import time
    import traceback
    from src.visualization.server import create_app

    try:
        print("[E2E TEST CHILD] Creating uvicorn config")
        config = uvicorn.Config(
            app=create_app(),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
        )
        server = uvicorn.Server(config)

        import threading
        def run_uvicorn():
            try:
                print("[E2E TEST CHILD] Starting uvicorn server.run()")
                server.run()
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[E2E TEST CHILD] Exception in uvicorn thread: {tb}")
                ready_conn.send(f"EXCEPTION: {tb}")

        threading.Thread(target=run_uvicorn, daemon=True).start()

        # Wait for /healthz to be ready (max 10s)
        url = f"http://127.0.0.1:{port}/healthz"
        for i in range(100):
            try:
                resp = requests.get(url, timeout=0.5)
                print(f"[E2E TEST CHILD] /healthz attempt {i+1}: {getattr(resp, 'status_code', None)}")
                if resp.status_code == 200:
                    ready_conn.send("READY")
                    break
            except Exception as e:
                print(f"[E2E TEST CHILD] /healthz attempt {i+1} failed: {e}")
            time.sleep(0.1)
        else:
            print("[E2E TEST CHILD] /healthz never became ready, sending FAIL")
            ready_conn.send("FAIL")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[E2E TEST CHILD] Exception in run_server: {tb}")
        ready_conn.send(f"EXCEPTION: {tb}")