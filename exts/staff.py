import argparse
import shlex

import discord
from discord.ext import commands

from params import Roles, Webhooks, Channels


class BasicHelpCommand(commands.MinimalHelpCommand):
  def get_destination(self):
    if self.cog is None:
      return super().get_destination()

    return self.cog.management_channel

  async def send_group_help(self, group):
    if self.cog is None or group.name not in self.cog.parsers:
      return await super().send_group_help(group)

    return await self.send_command_help(group)

  async def send_command_help(self, command):
    if self.cog is None or command.name not in self.cog.parsers:
      return await super().send_command_help(command)

    help_text = self.cog.parsers[command.name].format_help()
    destination = self.get_destination()
    await destination.send(f'```bash\n{help_text}```')


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

    self.proficiency_roles = Roles.group_proficiency
    self.dialect_roles = Roles.group_dialect
    self.enabled_roles = Roles.group_dialect + Roles.group_proficiency + Roles.group_normal

    self._help_command = bot.help_command
    bot.help_command = BasicHelpCommand(
        commands_heading='commands',
        aliases_heading='aliases',
        no_category='no category'
    )
    bot.help_command.cog = self

    self.setup_parser()

  def setup_parser(self):
    self.parsers = {}

    user = InteractiveArgumentParser(prog=self.bot.command_prefix + 'user')
    self.parsers['user'] = user

    subparsers = user.add_subparsers(
        title='subcommands', help='subcommand name', required=True
    )

    action_parser = InteractiveArgumentParser(add_help=False)
    action_parser.add_argument('-r', '--reason')

    ban = subparsers.add_parser(
        'ban', help='ban a user', parents=[action_parser]
    )
    ban.add_argument('users', type=int, nargs='+', help='user IDs')
    ban.add_argument(
        '-d', '--delete-history', type=int, choices=range(0, 2), default=0
    )
    self.parsers['ban'] = ban

    role = subparsers.add_parser(
        'role', help='toggle a role', parents=[action_parser]
    )
    role.add_argument('user', type=str, help='user ID, username or tag')
    role.add_argument('role', type=str, help='role ID or name')
    self.parsers['role'] = role

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

  async def cog_before_invoke(self, ctx):
    if ctx.command and ctx.command.name in self.parsers:
      ctx.parser = self.parsers[ctx.command.name]

  async def cog_after_invoke(self, ctx):
    if not self.in_management(ctx):
      return await ctx.message.delete()

  @commands.command()
  async def staff(self, ctx):
    """Toggle the `@staff` role."""

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

  @commands.group(aliases=['u'])
  async def user(self, ctx):
    """User commands."""
    pass

  @user.command(name='ban', aliases=['banir'])
  @commands.cooldown(rate=6, per=3600, type=commands.BucketType.member)
  async def user_ban(self, ctx, *, cmd: shlex.split = ''):
    """Ban users."""
    args = ctx.parser.parse_known_args(cmd)[0]

    users = []
    for user_id in args.users:
      try:
        u = await commands.UserConverter().convert(ctx, str(user_id))
      except:
        u = discord.Object(user_id)
      finally:
        if u:
          users.append(u)

    reason = f'[{ctx.author}] “{args.reason}”'

    logentry = discord.Embed(
        timestamp=ctx.message.created_at,
        colour=discord.Colour.orange(),
    )
    logentry.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

    for user in users:
      try:
        await ctx.guild.ban(
            user, reason=reason, delete_message_days=args.delete_history
        )
        logentry.description = f'{ctx.author.mention} banned ({user}) for “{args.reason}”'
        await self.logger_webhook.send(embed=logentry)
      except Exception as err:
        await self.management_channel.send(
            f'```bash\nfailed to ban ({user}): {err}```'
        )

  @user_ban.error
  async def user_ban_err(self, ctx, err):
    channel = ctx.channel
    if not self.in_management(ctx):
      channel = self.management_channel

    if isinstance(err, commands.MissingAnyRole) \
      or isinstance(err, commands.MissingPermissions):
      return

    return await channel.send(f'{ctx.author.mention}\n```bash\n{err}```')

  @user.command(name='role', aliases=['cargo'])
  @commands.cooldown(rate=24, per=3600, type=commands.BucketType.member)
  async def user_role(self, ctx, *, cmd: shlex.split = ''):
    """Give a role."""
    args = ctx.parser.parse_known_args(cmd)[0]

    try:
      user = await commands.MemberConverter().convert(ctx, str(args.user))
    except Exception as err:
      raise commands.ArgumentParsingError(
          f'Invalid member ({args.user}): {err}'
      )

    try:
      role = await commands.RoleConverter().convert(ctx, str(args.role))
    except Exception as err:
      raise commands.ArgumentParsingError(f'Invalid role ({args.role}): {err}')

    if role.id not in self.enabled_roles:
      raise commands.ArgumentParsingError(f'Invalid role {role} ({args.role})')

    reason = f'[{ctx.author}] “{args.reason}”'

    logentry = discord.Embed(
        timestamp=ctx.message.created_at, colour=discord.Colour.green()
    )
    logentry.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

    roles_to_add = []
    roles_to_remove = []
    roles_action = 'added'

    for user_role in user.roles:
      if user_role.id == role.id:
        roles_action = 'removed'
        roles_to_remove.append(role)
        logentry.colour = discord.Colour.orange()
        break
    else:
      roles_to_add.append(role)
      if role.id in self.proficiency_roles:
        for user_role in user.roles:
          if user_role.id in self.proficiency_roles:
            roles_to_remove.append(user_role)

    logentry.description = f'{ctx.author.mention} {roles_action} role ({user}, {role}) “{args.reason}”'

    if roles_to_add:
      await user.add_roles(*roles_to_add, reason=reason)

    if roles_to_remove:
      await user.remove_roles(*roles_to_remove, reason=reason)

    return await self.logger_webhook.send(embed=logentry)

  @user_role.error
  async def user_role_err(self, ctx, err):
    channel = ctx.channel
    if not self.in_management(ctx):
      channel = self.management_channel

    if isinstance(err, commands.MissingAnyRole) \
      or isinstance(err, commands.MissingPermissions):
      return

    return await channel.send(f'{ctx.author.mention}\n```bash\n{err}```')

  def cog_unload(self):
    self.bot.help_command = self._help_command


def setup(bot):
  bot.add_cog(Staff(bot))
