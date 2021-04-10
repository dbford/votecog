import hmac
from typing import Optional, Callable, Awaitable

from aiohttp import web

from git_vote_cog.config import WebhookConfig
from git_vote_cog.util import LOG


class HttpServer:
    app: web.Application
    runner: Optional[web.AppRunner]
    site: Optional[web.TCPSite]
    running: bool

    def __init__(self):
        self.app = web.Application()
        self.running = False

    @property
    def can_start(self) -> bool:
        return self.runner is None and self.site is None

    async def start(self, host: Optional[str] = None, port: int = 0):
        if self.running:
            return

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, host=host, port=port, shutdown_timeout=2.0)
        await self.site.start()

        self.running = True

    async def stop(self):
        if not self.running:
            return

        await self.site.stop()
        await self.runner.shutdown()
        await self.runner.cleanup()

        self.running = False


class LabelEvent:
    def __init__(self, repo_name: str, pull_request_id: int, label: str, added: bool):
        self.repo_name = repo_name
        self.pr_id = pull_request_id
        self.label_name = label
        self.label_added = added


class Webhook:
    def __init__(self, config: WebhookConfig, callback: Callable[[LabelEvent], Awaitable[None]]):
        self.http: Optional[HttpServer] = None
        self.config = config
        self.callback = callback
        self.secret = self.config.secret.encode('UTF-8')

    async def _verify_event(self, request: web.Request):
        header_signature = request.headers.get('X-Hub-Signature')
        if header_signature is None:
            return web.Response(status=403)

        sha_name, signature = header_signature.split('=')
        body = await request.read()
        mac = hmac.new(self.secret, msg=body, digestmod=sha_name)
        if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
            LOG.error("Invalid webhook event payload signature!")
            return web.Response(status=403)

        await self._handle_event(await request.json())

    async def _handle_event(self, body: dict):
        if body["action"] == 'labeled' or body["action"] == "unlabeled":
            pr_id = int(body["pull_request"]["number"])
            label = body["label"]["name"]
            repo_name = body["repository"]["full_name"]
            added = body["action"] != 'unlabeled'

            event = LabelEvent(repo_name, pr_id, label, added)
            await self.callback(event)

    def _setup_http(self):
        http = HttpServer()
        self.http = http

        async def say_hello(request: web.Request):
            return web.Response(text='Hello, World!')

        http.app.add_routes([web.get('/', say_hello)])
        http.app.add_routes([web.post(self.config.path, self._verify_event)])

        pass

    @property
    def running(self):
        return self.http is not None and self.http.running

    async def start(self):
        if self.running:
            return

        LOG.info(
            f"Starting webhook on http://{self.config.host if self.config.host is not None else 'localhost'}:{self.config.port}{self.config.path}")
        self._setup_http()
        await self.http.start(host=self.config.host, port=self.config.port)

    async def stop(self):
        if not self.running:
            return

        LOG.info("Stopping webhook")
        await self.http.stop()
