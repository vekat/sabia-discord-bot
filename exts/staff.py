import discord
from discord.ext import commands

from params import Roles, Webhooks, Channels


class Staff(commands.Cog):
  """Staff moderation commands."""
  def __init__(self, bot):
    self.bot = bot

    self.staff_role = Roles.staff
    self.required_roles = Roles.helpers
    self.logger_webhook = Webhooks.moderation
    self.management_channel = Channels.management

  @commands.Cog.listener()
  async def on_ready(self):
    guild = self.bot.main_guild

    if type(self.logger_webhook) is int:
      self.logger_webhook = await self.bot.fetch_webhook(self.logger_webhook)

    if type(self.staff_role) is int:
      self.staff_role = guild.get_role(self.staff_role)

    if type(self.management_channel) is int:
      self.management_channel = guild.get_channel(self.management_channel)

    print('→ staff module ready')

  def in_management(self, ctx):
    return ctx.channel.id == self.management_channel.id

  async def cog_check(self, ctx):
    if ctx.author.id == ctx.guild.owner_id:
      return True

    for role in ctx.author.roles:
      if role.id in self.required_roles:
        return True

    raise commands.MissingAnyRole(self.required_roles)

  async def cog_after_invoke(self, ctx):
    if not self.in_management(ctx):
      return await ctx.message.delete()

  @commands.command()
  async def staff(self, ctx):
    if not self.in_management(ctx):
      raise commands.CheckFailure('Invalid channel', self.management_channel.id)

    logentry = discord.Embed(
        title='enabled staff',
        timestamp=ctx.message.created_at,
        colour=discord.Colour.green()
    )
    logentry.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

    for role in ctx.author.roles:
      if role.id == self.staff_role.id:
        await ctx.author.remove_roles(role)

        logentry.title = 'disabled staff'
        logentry.colour = discord.Colour.orange()
      else:
        await ctx.author.add_roles(self.staff_role)

    return await self.logger_webhook.send(embed=logentry)


def setup(bot):
  bot.add_cog(Staff(bot))
