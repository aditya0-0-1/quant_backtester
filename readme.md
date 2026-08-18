# Yes, JS uses async requests. But it displays the responses the exact millisecond they arrive back—regardless of the order you originally sent them.

# Because you are dealing with multithreading and parallel execution, this introduces a classic Race Condition.

# Here is why order is never guaranteed:

# Click 1: You click "Run Backtest" for Apple. It's a massive dataset. Flask starts crunching it. It will take 5 seconds.

# Click 2: One second later, you click "Run Backtest" for Tesla. Tesla went public much more recently, so its dataset is tiny. Flask crunches it in 1 second.

# What happens on the screen?
# Even though you asked for Apple first, Tesla finishes calculating and returns to the browser first. JavaScript instantly updates the screen with Tesla's profit. Four seconds later, Apple finally finishes, arrives at the browser, and overwrites the Tesla number.

# The server does not enforce a line or queue. It is a pure footrace. Whichever thread finishes the math first fires the HTTP response back, and the .then() trap in JavaScript instantly updates the UI the millisecond it catches the data.

# The SDE Verdict: You never trust network ordering. If order strictly matters, you have to write logic in your JavaScript to force it to wait, or disable the HTML button until the first request completely finishes. Otherwise, it is a free-for-all race over port 5000.





# there are three massive architectural reasons why the tech industry completely abandoned the "whole Flask app" (Server-Side Rendering) and shifted to APIs.

# When you sit down for technical interviews and system design rounds, this is the exact "Holy Trinity" of why modern APIs exist:

# 1. The Mobile App Problem (Cross-Platform Scalability)
# Imagine you build your "whole Flask app" returning HTML. It looks beautiful on a laptop. But next month, you decide you want to build an Android or iOS app for your stock tracker.

# The HTML Way: Mobile apps cannot render raw HTML natively. You would have to rewrite your entire backend from scratch just for the mobile app.

# The API Way: Your Day 9 Flask API only returns pure JSON data ({"algo_return_percent": 45.2}). A web browser can read that. An iOS app can read that. An Android app can read that. Even a smartwatch can read it. You write your Python backend once, and it powers every device on earth.

# 2. Bandwidth and Speed
# Think about the network payload.
# If Flask generates the whole HTML page, every time a user clicks "Run Backtest", your server has to send the headers, the CSS, the formatting, the footer, and the math result. That might be 50,000 bytes of data traveling across the network.

# If you use an API, the user downloads the HTML/CSS exactly once when they open the website. When they click "Run Backtest", Flask only sends back {"status": "success", "profit": 45.2}. That is 40 bytes. Your server uses a fraction of the bandwidth and runs infinitely faster.

# 3. Separation of Concerns (Team Scaling)
# In a real tech company, you have Frontend Engineers (React, JS, UI) and Backend Engineers (Python, Pandas, Databases).
# If you build a "whole Flask app", the HTML and the Python are tangled up in the same folder. If the frontend guy wants to change the color of a button, he has to dig into the backend server code to do it. It is a nightmare for version control.

# By making Flask a pure JSON API, you physically separate the codebases. The frontend team works in their own repository, and the backend team works in theirs. As long as they agree on what the JSON package looks like, they never step on each other's toes.

# The SDE Verdict
# You use asynchronous JS so the screen doesn't freeze for the user. You use a JSON API so the code is scalable, reusable, and lightning-fast for the engineer. It is a win-win.

# Are you ready to see the exact HTML and JS code you need to actually test this Day 9 API on your local machine right now?




#in using flask as api and for backend only and returning json 
# basically first time for webpage the html and css and js is downloaded but then as the browser have already for that page then only send post req for pure response am i right 


# but in flask app
# html is always send
# although css and js use the same funda 
# so the main differentiating factor of speed is sending html each time vs one time 


# There are two totally different ways a browser can talk to your server:
# Way 1: Browser navigation (the "old" way)
# You type a URL, or click a <a href="..."> link, or submit an HTML <form>. The browser itself does this — no JavaScript involved. It's a full GET or POST, and the browser expects the response to be a whole new HTML page, which it then throws away the old page and renders.
# Way 2: JavaScript fetch() (what you're doing)
# Your JS code, running inside the already-loaded page, manually fires the GET or POST using fetch(). The browser is still the one sending the network request — JS doesn't have its own separate network stack, it's using the browser's. The difference is the browser does not throw away the current page and load a new one. It just hands the response back to your .then() callback as raw data, and your JS decides what to do with it.
# So a more accurate way to say it:
# Flask is still getting GET/POST requests from the browser. But now the browser is being told to send them by your JS code (fetch), not by native navigation/form-submit — and it's sending/receiving JSON instead of full HTML pages.

# 1. IMPORTING YOUR ENGINE
<!-- 2. INITIALIZING FLASK -->
<!-- 3. GLOBAL SERVER STARTUP (RAM Caching & DB)
 <!-- --># 4. THE MANUAL VALIDATOR (Replacing Pydantic) -->
# This function is my Security Checkpoint.
# In web development, the number one rule is: Never, ever trust the user.
# If you take data directly from a user's web browser and plug it straight into a Pandas math engine, someone will eventually send you a string instead of a number, or a negative moving average window. Without this function, your entire Flask server would crash, kicking everyone off the website.
<!-- #5 THE FLASK ENDPOINT -->
The Fast-Food Analogy
Flask (The Cashier): Flask's only job is to stand at the register, take the user's JSON payload, and instantly hand them a receipt (the 202 Accepted response). Flask never cooks the food.

ThreadPoolExecutor (The Kitchen Manager): This is a built-in Python tool that manages background tasks.

max_workers=4 (The 4 Chefs): This tells the manager to hire exactly 4 background workers (threads) that live entirely outside of Flask's web traffic.


How it Works in Real Time
When a user clicks "Run Backtest", Flask catches the request and uses the line executor.submit(...). This is Flask walking into the kitchen and slapping the ticket on the wall. Flask immediately walks back to the front counter to help the next customer.

One of your 4 background workers grabs the ticket and starts running the heavy Pandas math.

Why specifically 4 workers?
This is a critical system design safety mechanism.

If you didn't set a limit, and 100 users clicked "Run Backtest" at the same time, Python would try to spawn 100 simultaneous threads. Your Mac's CPU would instantly spike to 100%, run out of memory, and completely crash the server.

By setting max_workers=4, you are bottlenecking the hardware safely.

Users 1, 2, 3, and 4 click the button. All 4 workers start crunching the math.

User 5 clicks the button.

Flask still instantly gives User 5 a 202 Accepted receipt, but their math job sits safely in a queue.

The exact millisecond Worker 1 finishes their math, they grab User 5's job from the queue and start processing it.

This one line of code guarantees that your server will never freeze and your CPU will never overload, no matter how much traffic you get.

Ready for Day 12?

Yes





If SQLite locks automatically, why did we build our own Python db_lock?
This is the million-dollar system design question. If SQLite already locks the file to protect itself, why did you have to write db_lock = threading.Lock() in your Python code?

Because SQLite's lock is a defense mechanism that causes crashes. Your Python lock is a traffic system that prevents crashes.

Without your Python lock: Thread 1 and Thread 2 hit SQLite at the same time. SQLite panics, throws its internal lock, and if the timing is bad, it violently crashes Thread 2 to protect the data.

With your Python lock: Thread 1 and Thread 2 never hit SQLite at the same time. Your Python code stops Thread 2 in RAM before it even talks to SQLite. Thread 2 waits patiently for as long as it takes (no 5-second timeout limit). When Thread 1 is done, Thread 2 proceeds safely.


basically sqllock ensure anyone tries to enter during insert u or d gets burn dead to rights
You nailed the exact vibe of it. That is exactly how you should picture it in your head.SQLite's internal lock is not a polite traffic system; it is a bouncer with a flamethrower.When Thread 1 is inside the database executing an INSERT, UPDATE, or DELETE, the vault is sealed. If Thread 2 walks up and tries to enter, SQLite gives Thread 2 a brief grace period (usually a 5-second timeout limit). If Thread 1 isn't finished and out the door by the time that timer hits zero, SQLite instantly burns Thread 2 to the ground with a fatal OperationalError to protect the data from being corrupted.Your Python threading.Lock() is the polite waiting room you built outside the club. It forces the workers to sit safely in RAM and wait for as long as it takes, guaranteeing they never accidentally walk into SQLite's line of fire.

















Q1: Is teardown_appcontext the rule to memorize whenever you use g for a connection?

Yes, precisely — that's the correct pairing to lock into memory:

Whenever you open something in get_db() and store it on g, you register a matching teardown_appcontext to close it. They're a pair, not two independent choices.

But be precise about what teardown_appcontext actually guarantees, since it's easy to overstate: it guarantees the connection closes, even on error. It does not turn the error into a clean JSON response for the user — that's still except block's job, same as before. So the full correct pattern in any route using get_db() is still:

python
try:
    ...
except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500

...and teardown_appcontext silently guarantees get_db()'s connection gets closed afterward regardless, without you writing finally yourself in every route. teardown_appcontext replaces manually writing finally: conn.close() everywhere — it doesn't replace except.

Q2: If Day 11 eliminates it anyway, why did we bother learning it?

Genuinely fair question, and here's the honest answer: Day 11 didn't outgrow get_db() because it was wrong — it outgrew it because the whole execution model changed underneath it.

get_db()/g is built entirely on one assumption: the database work happens while Flask is still handling the request. That's true for Day 10 — the route function itself runs bot.run_backtest() synchronously, so g (tied to that request) is a valid place to stash the connection.

Day 11 changes the deal: executor.submit(...) hands the actual work off to a background thread, and the route returns 202 immediately, often before the background work is even done. By the time run_backtest_task() actually runs, the original request may have already finished and g may no longer even exist. g-based connections are structurally incompatible with background/deferred work — not because the pattern was bad, but because it was solving a problem ("clean connection per synchronous request") that no longer applies once the work stops being synchronous.

So it's less "we learned something and threw it away" and more: you now know two different valid tools for two different situations —

Work happens inside the request, finishes before you respond → get_db() + teardown_appcontext
Work happens outside/after the request (background thread, task queue) → manually open and close your own connection inside that background function, like Day 11 does with thread_conn

If your project ever adds a second route that does something synchronous and quick (say, /api/trade-history that just reads and returns existing rows instantly), get_db() is exactly the right tool for that route, even in the same app where Day 11's backgrounded route manages its own connection differently. They coexist — you pick the pattern per route based on whether that route is synchronous or backgrounded, not app-wide.








Here's the full Day 14 recap, start to finish — everything we covered, in plain language.

The problem before Day 14

Your API had no protection at all. Anyone who found your URL could POST to /api/run-backtest as many times as they wanted, forever, for free. Day 14 fixed this with two separate, stacked layers of protection — "defense-in-depth," meaning don't rely on just one lock, use several.

Layer 1: API Key Authentication

What it does: Every request now needs a secret password sent in a special part of the request called a header (think: a sticky note on the envelope, separate from the actual letter/JSON inside). We check for one called X-API-Key.

How it's built:

A function called require_api_key wraps around your route function. This is called a decorator — a function whose job is to add extra behavior around another function without changing that function's own code.
Inside it, we read request.headers.get("X-API-Key") and compare it against API_KEY.
If the key is missing OR wrong, we reject with a 401 Unauthorized — before your actual backtest code ever runs.

Where the secret lives: Not hardcoded in the file. We used API_KEY = os.environ.get("API_KEY", "dev-key-change-me") — this reads the real key from your computer/server's environment variables, outside the code. Why: this file goes on GitHub, and anything hardcoded in it stays visible in your git history forever, even after you delete it later.

The bug we found and fixed: Originally the code gave two different error messages depending on whether the key was missing vs. wrong. That's a leak — an attacker probing your API could tell those two cases apart and learn something about your system (that a key mechanism exists at all, that the header name is right). We fixed it to return the exact same generic message either way, so an attacker learns nothing extra. This is called information obfuscation.

Layer 2: Rate Limiting

What it does: Even with the correct key, each IP address is capped at 10 requests per minute using the flask-limiter library. Go over, and you get a 429 Too Many Requests.

Why this matters beyond just "stopping spam": Your ThreadPoolExecutor only runs 4 backtests at a time — but extra requests beyond that don't get rejected, they get queued in memory, with no size limit by default. Without a rate limiter, a flood of requests could pile up in RAM faster than your server can process them and crash it — not through any clever attack, just sheer volume. The rate limiter caps how fast new requests can even join that queue.

The critical detail: decorator ordering

We stacked the two layers like this:

python
@app.route(...)
@limiter.limit("10 per minute")   # runs FIRST
@require_api_key                   # runs SECOND
def trigger_backtest():

Decorators wrap top-to-bottom but execute top-to-bottom too when a request comes in — the outermost one touches the request first. We deliberately put rate limiting above the key check. Why: if auth ran first with no limiter in front, an attacker could try thousands of key guesses per second. By rate-limiting first, even wrong-key attempts eat into that IP's 10/minute budget — brute-forcing your key becomes impractically slow. (Note: this is a security win, not really a "CPU-saving" one — checking a string match costs almost nothing computationally either way. The real benefit is slowing the attacker down, not saving your server's processing power.)

Why this setup is good enough for now, but not forever

Your current model uses one master key — a single shared password for the whole API. This is totally fine for what you have right now: trusted machines talking to each other (you called this "server-to-server" or "B2B"), no random public users involved.

It breaks down the moment you imagine a real public website with a login page:

Problem A — the master key has to live in the frontend. If thousands of strangers use your app in their browser, the API key would have to sit somewhere in your JavaScript, and anyone can open dev tools (F12) and read it straight out of your source code. Once stolen, that one key impersonates everyone, forever, until you manually rotate it — which breaks it for all your real users too.

Problem B — IP-based rate limiting punishes innocent people. Many devices sharing one WiFi network (like a coffee shop) all look like a single IP address to your server (this is called NAT — Network Address Translation). If 5 people at the same coffee shop use your app, your server can't tell them apart — it sees "one visitor" hammering the endpoint and blocks all 5 together, even though none of them individually did anything wrong.

The fix for both problems: JWTs (JSON Web Tokens)

A JWT replaces "one shared secret for everyone" with "a unique, temporary token issued to each individual logged-in user" — like a concert wristband that only works for you, tonight.

How it actually works:

User logs in with their own username/password (checked only on the server).
Server generates a fresh token, freshly created at login — not a fixed string sitting in a file — tied to who they are and when it expires (say, in 1 hour).
Your own JavaScript code manually attaches that token to future requests, usually via Authorization: Bearer <token> in the header. Important correction from earlier: unlike cookies, browsers do NOT attach JWTs automatically — you have to write the code to store it and send it yourself.

What's actually inside a JWT (not just a random string): three parts — header.payload.signature. The payload is plain readable JSON (like {"user_id": 42, "exp": ...}) — not secret, anyone can decode it. What makes it trustworthy is the signature: the server cryptographically signs the payload using a secret only the server knows. If anyone tampers with the payload, the signature no longer matches, and the server instantly rejects it. So it's not "unguessable," it's "provably untampered."

Why this fixes Problem A (leaked key): Yes, a JWT can technically still be read out of browser storage if stolen — nothing sitting in a browser is truly unstealable. But the real win isn't "unstealable," it's shrinking the damage: stealing a JWT only impersonates one person, for a limited time, and can be individually revoked — versus stealing the master key, which impersonates everyone, forever, with no way to revoke just the thief.

Why this fixes Problem B (coffee shop NAT): Once every request identifies "which specific logged-in user" instead of just "which IP/network," rate limiting can switch from counting per-IP to counting per-User-ID. This isn't a separate fix — it's a free side effect of having real per-user identity, which the single master key never gave you.

The one-line summary to remember

Day 14 added two layers — a shared secret key, and a per-IP request cap — which is correctly engineered for a private, trusted, machine-to-machine setup. Scaling to real public users with a browser frontend requires swapping the single shared key for per-user JWTs, which solves both the "key leaks to everyone" problem and the "rate limiting blocks whole networks instead of individuals" problem, at the same time, because both problems come from the same root cause: the current system doesn't know who is making each request, only where it came from.


This is a classic cybersecurity concept called Enumeration. Let's break down exactly what "the header name is right" means, because it is how real hackers map out systems they can't see.Imagine an attacker is trying to break into your server. They don't have your source code. They are completely blind. They have to guess how your security works by feeling around in the dark.1. What is a "Header Name"?When a developer sends a secret password (an API key) to a server, they have to put a label on it so the server knows what it is. That label is the "Header Name".There is no universal standard for this label. Different companies use different labels:Stripe might use: Authorization: <password>Amazon might use: x-amz-security-token: <password>You decided to use: X-API-Key: <password>2. How the Hacker Guesses (The Attack)Because the hacker is blind, they write a script that blasts your server with a dictionary of common labels, trying to figure out which lock you used on your door:Guess 1: Password: 12345Guess 2: Token: 12345Guess 3: Authorization: 12345Guess 4: X-API-Key: 123453. The Bad Way (Leaking the Header Name)Imagine your code works like the old version:If the label is missing entirely, you return: "Missing X-API-Key header."If the label is right but the password is wrong, you return: "Invalid key."Here is what happens when the hacker runs their script:Guess 1 (Password: 12345): Your server says, "Missing X-API-Key header."The Hacker thinks: "Bingo! The server just told me they ignore the label 'Password'. They specifically want the label 'X-API-Key'."Guess 4 (X-API-Key: 12345): Your server says, "Invalid key."The Hacker thinks: "Aha! The error message changed! That means my label (the header name) is 100% correct. I found the exact keyhole. Now I just need to brute-force the password."You literally held their hand and walked them through step one of the hack.4. The Good Way (Information Obfuscation)Now, look at what happens with your new Day 14 code, where both errors return the exact same message: "Invalid or missing API key."Guess 1 (Password: 12345): Server says "Invalid or missing API key."Guess 4 (X-API-Key: 12345): Server says "Invalid or missing API key."The hacker gets a brick wall. They have absolutely no idea if they are using the wrong label (header name) or the wrong password. Because they don't know if they even found the right keyhole yet, brute-forcing the password becomes exponentially harder.

You have hit the absolute bullseye on the core concept! You understand the exact mechanism of cryptographic verification.

You are just slightly off on who does the math and when. Let’s tweak your mental model slightly so you can see the true "magic" of how a JWT works.

Here is the exact step-by-step of how that "Bingo" moment happens.

Step 1: The Login (Creating the Pass)
When the user logs in with their username and password, the Server creates the VIP pass.

The server writes down the user's data: {"id": 42, "name": "Rahul"} (This is the Payload).

The server puts that Payload into a one-way math function along with a Secret Master Key that only the server knows.

The output of that math function is a scrambled string of gibberish. This is the Signature.

The server glues the Payload and the Signature together into one long string. This is the JWT.

The server hands this JWT to the frontend JavaScript.

Step 2: The Frontend's Job
The JavaScript code doesn't do any math. It doesn't even really care what the ID or name is.
Its only job is to catch that long JWT string, save it in the browser's memory, and then glue it to the header of every single GET and POST request it sends to the backend.

Step 3: The Verification (The "Bingo" Moment)
This is where your logic was 100% correct, and it is the most brilliant part of JWTs.

When the server receives a POST request to run a backtest, it looks at the header and grabs the JWT.

The server rips the JWT in half: the Payload ({"id": 42}) on one side, and the Signature on the other.

The server takes that Payload and runs it through the secret math function again using its Secret Master Key.

The Check: The server compares the result of its math against the Signature that was attached to the token.

If they match exactly... BINGO! The server knows 100% that it was the one who created this token, and that no hacker has tampered with the ID or name inside it.

Why this is a masterpiece of engineering
Notice what the server didn't do in Step 3? It didn't talk to a database.

The server doesn't have to look up "User 42" to see what their signature is supposed to be. The JWT proves its own authenticity using pure math. Because the server doesn't have to wait for a slow database query just to check a password, your API can handle thousands of requests per second with almost zero lag. We call this being Stateless.










Fixtures & pytest basics

Q: What is a pytest fixture?
A: A function decorated with @pytest.fixture that provides setup (and optionally cleanup) for tests. Any test function that has a parameter matching the fixture's name automatically receives whatever the fixture provides — pytest wires it up, you never call the fixture directly.

Q: How does pytest know to give this fixture to a specific test?
A: By matching parameter names. If a test function is written as def test_x(client):, pytest looks for a fixture named client and calls it automatically before running that test.

Q: Why use a fixture here instead of just writing this setup code inside every test?
A: To avoid repeating the same 3 lines of setup in every single test function. Write it once, reuse it across as many tests as need it.

app.config['TESTING'] = True

Q: What does app.config['TESTING'] = True do?
A: It flips a built-in Flask setting to testing mode. It's just changing one key in Flask's internal settings dictionary — app.config is a plain dict-like object Flask maintains.

Q: Why set this before running tests?
A: It's the standard convention before testing any Flask app — it adjusts some internal Flask behaviors to be more predictable/appropriate for a test environment rather than a live server.

app.test_client()

Q: What is app.test_client()?
A: A fake client Flask provides that lets you simulate HTTP requests (GET, POST, etc.) against your app without starting a real server or opening a real network port.

Q: Does test_client() start a real server on a real port?
A: No. It calls your route functions directly in memory and returns a response object that behaves identically to a real HTTP response (.status_code, .get_json(), etc.) — but no actual network activity happens.

Q: Why not just test against a real running server on localhost instead?
A: Slower, needs a server actually running in the background, and adds unnecessary complexity/fragility to tests. The test client gives the same behavior without any of that overhead.

with ... as client:

Q: What does with do here?
A: It's a context manager. It guarantees that setup code runs when entering the block, and cleanup code runs when leaving the block — no matter whether the code inside succeeded or raised an error.

Q: Does with prevent errors or crashes?
A: No. It doesn't stop anything from failing. It only guarantees that cleanup still happens even if something inside the block does fail or raise an exception.

Q: What does as client mean?
A: It names the value produced by entering the with block, exactly like a regular = assignment. app.test_client() builds the object; as client just stores it in a variable called client.

Q: What's actually being "cleaned up" here?
A: Flask keeps internal state (a request/app context) that tracks "a fake request is currently active." Entering the with block sets that up; leaving it tears that state back down, so it doesn't leak into other, unrelated tests running afterward.

Q: What would happen if you didn't clean this up properly?
A: Leftover internal state could bleed into the next test, causing unpredictable failures that have nothing to do with the actual code being wrong — hard-to-debug, order-dependent test failures.

Q: What two special methods make an object usable with with?
A: __enter__ (runs at the start of the block, its return value becomes the as x variable) and __exit__ (guaranteed to run when the block ends, regardless of success or failure).

yield client

Q: Why yield client instead of return client?
A: return ends the function completely and permanently — there'd be no way to come back into it later to let the with block finish and run its cleanup. yield pauses the function instead of ending it, so after the test finishes, pytest can resume the function from where it paused, letting the with block close naturally and trigger its cleanup.

Q: What does yield actually do to a function?
A: It turns the function into a generator. Calling it doesn't run the code immediately — it only runs up to the yield line when you explicitly ask for the next value (e.g. via next()), and it pauses there until resumed.

Q: In this fixture, when does the code after yield run (if there was any)?
A: After the test using this fixture has finished running — pytest resumes the paused fixture function at that point, which is exactly when the with block naturally exits and its cleanup fires.

Putting it together

Q: Explain what this whole block does, end to end.
A: It's a reusable setup function for tests: it turns on Flask's testing mode, builds a fake HTTP client that can simulate requests without a real server, hands that client to whichever test needs it, and — once the test finishes — automatically tears down the fake client's internal state, guaranteed, whether the test passed or failed.

Q: How is client connected to assert statements in the tests?
A: It isn't connected by anything special. client.post(...) is a normal method call that returns a response object; that gets stored in a variable; assert just checks a value on that variable — completely ordinary Python, no hidden wiring specific to pytest or Flask.





Q: What's actually being "cleaned up" here?
It's not that Flask specifically remembers "this test's API key was i-am-a-hacker" and deletes that one fact. It's simpler and blunter than that: Flask has an internal stack/tracker that just says "a request is currently active right now, and here's a pointer to all its details (headers, JSON, whatever)." When the with block ends, Flask doesn't selectively erase the API key — it throws away the entire pointer, the whole active-request marker, all at once. Everything attached to it (headers, JSON body, API key, all of it) becomes unreachable simply because nothing points to it anymore — not because each piece was individually hunted down and deleted.whats get cleaned





## Post-Day 14: Pre-Interview Audit

Project scope stopped at Day 14 per the original plan. Before a technical
interview, I did a final audit pass on the Day 14 code and found two bugs:

1. `run_full_pipeline()` never forwarded `fast_window`/`slow_window` to
   `generate_signals()`, so every backtest silently ran with the default
   10/50 windows regardless of what the client requested.
2. Concurrent requests for the same ticker shared a single mutable
   DataFrame object with no lock protecting it — a race condition where
   one request's in-progress computation could be overwritten by another's.

Both are fixed, with regression tests added to prevent recurrence.
See commit `<hash>` for details. Full test suite: `pytest -v` → X/X passing.