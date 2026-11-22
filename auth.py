from playwright.sync_api import sync_playwright

def get_fresh_bearer_token(session_name="amis_session"):
    """
    Launches a persistent browser session to intercept the Bearer Token 
    from the UPLB AMIS network traffic.

    session_name: name of the folder used to save this login. Use a
    different session_name per account if you switch accounts often,
    e.g. get_fresh_bearer_token("amis_session_myacc2"), so each account
    keeps its own saved login instead of overwriting the other.
    """
    print("Launching browser to intercept Bearer Token...")
    token = None
    
    with sync_playwright() as p:
        #launch a persistent context
        #it creates a folder to remember your Google Login for this account
        context = p.chromium.launch_persistent_context(
            user_data_dir=f"./{session_name}",
            #executable_path="/usr/bin/chromium"
            headless=False,  #keep this False so you can see it and log in if necessary
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()

        def intercept_request(request):
            nonlocal token
            #look for API requests to the UPLB AMIS backend
            if "api-amis.uplb.edu.ph/api" in request.url:
                auth_header = request.headers.get("authorization", "")
                if "Bearer " in auth_header:
                    token = auth_header.split("Bearer ")[1]

        #attach the network listener to the page
        page.on("request", intercept_request)

        #navigate to the UPLB AMIS login page
        page.goto("https://amis.uplb.edu.ph/") 
        
        try:
            #wait for the page to load and trigger the initial API calls
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass 

        #if token isn't found immediately, it means you need to log in manually
        if token is None:
            print("⚠️ Token not found. You likely need to log in.")
            print("⏳ Waiting up to 10 seconds... Please complete the login in the browser window.")
            #poll every 500ms for up to 60 seconds so we return as soon as token is captured


            #range(x) = seconds/2 so 120/2 = 60 seconds
            for _ in range(120):
                if token is not None:
                    break
                page.wait_for_timeout(500)
            
        context.close()
        
    return token