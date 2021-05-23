# VoteCog

A Discord-Github interop PR voting system - powered by RedBot. This cog enables discord users to vote on PRs being merged. Works by reading/writing labels on PRs. Webhook enabled for real-time voting with manual `!vote <PR#>` backup. Cog state is automatically saved/restored over RedBot start/stop.

### Dependencies

* pip install PyGithub
* pip install AioHttp
* pip install Red-DiscordBot

### Running

Run via standard cog setup documented here: https://docs.discord.red/en/stable/ . Bot must have manage message permissions on a "voting" channel. Confgiure in Discord with `!vote set` .





