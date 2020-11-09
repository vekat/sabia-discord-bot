import argparse
import shlex

import discord
from discord.ext import commands

from params import Roles, Webhooks, Channels


class InteractiveArgumentParser(argparse.ArgumentParser):
  def exit(self, status=0, message=None):
    if message:
      self._print_message(message)

  def error(self, message):
    self.exit(message=f'error: {message}\n{self.format_usage()}')

  def _print_message(self, message, file=None):
    if message:
      raise commands.ArgumentParsingError(message)


class Staff(commands.Cog):
  """Staff moderation commands."""
  def __init__(self, bot):
    self.bot = bot

    self.staff_role = Roles.staff
    self.required_roles = Roles.helpers
    self.logger_webhook = Webhooks.moderation
    self.management_channel = Channels.management

    p = InteractiveArgumentParser(prog='$ban')
    p.add_argument('user', type=int, help='user ID')
    p.add_argument('-r', '--reason', default='none')
    p.add_argument(
        '-d', '--delete_history', type=int, choices=range(0, 2), default=0
    )
    self.ban_parser = p

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
    """Toggle the @staff role."""

    logentry = discord.Embed(
        description=f'{ctx.author.mention} enabled staff',
        timestamp=ctx.message.created_at,
        colour=discord.Colour.green()
    )
    logentry.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

    for role in ctx.author.roles:
      if role.id == self.staff_role.id:
        await ctx.author.remove_roles(role)

        logentry.description = f'{ctx.author.mention} disabled staff'
        logentry.colour = discord.Colour.orange()
        break
    else:
      await ctx.author.add_roles(self.staff_role)

    return await self.logger_webhook.send(embed=logentry)

  @commands.group()
  async def user(self, ctx):
    """User commands."""
    pass

  @user.command(name='ban', aliases=['banir'])
  @commands.cooldown(rate=6, per=3600, type=commands.BucketType.member)
  async def user_ban(self, ctx, *, cmd: shlex.split = ''):
    """Ban a user. Use `$user ban --help` for details."""

    args = self.ban_parser.parse_known_args(cmd)[0]

    try:
      user = await commands.MemberConverter().convert(ctx, str(args.user))
    except Exception:
      user = discord.Object(args.user)

    reason = f'[{ctx.author}] “{args.reason}”'

    logentry = discord.Embed(
        timestamp=ctx.message.created_at,
        colour=discord.Colour.orange(),
        description=f'{ctx.author.mention} banned ({user}) for “{args.reason}”'
    )
    logentry.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

    await ctx.guild.ban(
        user, reason=reason, delete_message_days=args.delete_history
    )

    return await self.logger_webhook.send(embed=logentry)

  @user_ban.error
  async def user_ban_err(self, ctx, err):
    channel = ctx.channel
    if not self.in_management(ctx):
      channel = self.management_channel

    if isinstance(err, commands.MissingAnyRole) \
      or isinstance(err, commands.MissingPermissions):
      return

    return await channel.send(f'{ctx.author.mention}\n```bash\n{err}```')


def setup(bot):
  bot.add_cog(Staff(bot))
