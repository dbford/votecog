# VoteCog

A Discord-Github interop PR voting system - powered by RedBot. This cog enables discord users to vote on PRs being merged. Works by reading/writing labels on PRs. Webhook enabled for real-time voting with manual `!vote <PR#>` backup. Cog state is automatically saved/restored over RedBot start/stop.

### Dependencies

* pip install PyGithub
* pip install AioHttp
* pip install Red-DiscordBot

### Running

Run via standard cog setup documented here: https://docs.discord.red/en/stable/ . Bot must have manage message permissions on a "voting" channel. Confgiure in Discord with `!vote set` .

### License

```
Copyright 2021 Daniel Bradford

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.```
