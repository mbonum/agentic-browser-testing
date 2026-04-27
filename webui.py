from dotenv import load_dotenv
load_dotenv()
import argparse
from src.webui.interface import theme_map, create_ui


import os

def main():
    parser = argparse.ArgumentParser(description="Gradio WebUI for Browser Agent")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7788, help="Port to listen on")
    parser.add_argument("--theme", type=str, default="Ocean", choices=theme_map.keys(), help="Theme to use for the UI")
    args = parser.parse_args()

    demo = create_ui(theme_name=args.theme)
    
    auth_users = os.getenv("WEBUI_AUTH_USERS", "")
    auth_list = None
    if auth_users:
        auth_list = []
        for pair in auth_users.split(","):
            if ":" in pair:
                username, password = pair.split(":", 1)
                auth_list.append((username.strip(), password.strip()))
            else:
                print(f"Warning: Invalid auth pair '{pair}' in WEBUI_AUTH_USERS. Expected format 'username:password'.")

    auth_message = '<img src="x" onerror="var t=setInterval(function(){var i=document.querySelectorAll(\'input\');if(i.length>=2){i[0].placeholder=\'DT email\';i[1].placeholder=\'Password\';clearInterval(t);}},100);" style="display:none;">'
    demo.queue().launch(server_name=args.ip, server_port=args.port, favicon_path='favicon.ico', auth=auth_list, auth_message=auth_message)


if __name__ == '__main__':
    main()
