import discord
from discord.ext.commands import Bot

import params


class Sabia(Bot):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.main_guild = params.guild

  async def on_ready(self):
    print('→ online as:', self.user)
    print('→ discord.py:', discord.__version__)

    if type(self.main_guild) is int:
      try:
        self.main_guild = self.get_guild(self.main_guild)
      except Exception:
        self.logout()
        raise Exception('Invalid guild')

  async def on_command_error(self, ctx, err):
    if isinstance(err, discord.ext.commands.CommandNotFound
                 ) or isinstance(err, discord.ext.commands.CheckFailure):
      return

    print('→ command error:', err)


if __name__ == '__main__':
  bot = Sabia(
      command_prefix='$',
      activity=discord.Activity(
          name='The 7th Element', type=discord.ActivityType.listening
      )
  )

  exts = ['exts.staff']

  for ext in exts:
    try:
      bot.load_extension(ext)
      print('→ loaded extension:', ext)
    except Exception as err:
      print('→ failed extension:', ext, err)

  bot.run(params.token)
