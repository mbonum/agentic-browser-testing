1. Open the browser and go to the login page at `<base_url>/path>`
2. Click the `Login` button (or the main login link if the page starts elsewhere).
3. In the username field, type the value from the environment variable TEST_USERNAME (loaded from .env).
4. In the password field, type the value from the environment variable TEST_PASSWORD (loaded from .env).
5. Click the `Sign in` button.
6. Wait until the page navigates away from the login page.
7. Verify that the current URL contains /dashboard (or the expected post-login path).
8. Verify that the text `Welcome back` (or the expected greeting) is visible on the page.
9. Verify that a cookie named auth_token (or the session cookie used by the app) exists.
