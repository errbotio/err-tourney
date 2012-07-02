from datetime import datetime
import logging
from math import ceil, sqrt
from errbot.botplugin import BotPlugin
from errbot.jabberbot import botcmd

MAX_INCREASE = 32
INITIAL_SCORE = 1500

class Tourney(BotPlugin):
    min_err_version = '1.2.2' # for dictionary mixin
    def get_games(self):
        return self.get('games_record', [])

    def add_game(self, winner, looser):
        games = self.get_games()
        games.append((winner, looser, datetime.now()))
        self['games_record'] = games

    def get_players(self):
        return self.get('players', {})

    def add_players(self, name):
        players = self.get_players()
        players[name] = 1500
        self['players'] = players

    def remove_players(self, name):
        players = self.get_players()
        del players[name]
        self['players'] = players

    def add_game_result(self, winner, looser):
        players = self.get_players()
        self.add_game(winner, looser)
        winner_oldrank = players[winner]
        looser_oldrank = players[looser]

        elo_correction = MAX_INCREASE * 1 / (1 + 10 ** ((winner_oldrank - looser_oldrank) / 400))
        winner_rank = winner_oldrank + elo_correction
        looser_rank = looser_oldrank - elo_correction
        players[winner] = winner_rank
        players[looser] = looser_rank
        self['players'] = players
        return (winner_oldrank, winner_rank), (looser_oldrank, looser_rank)


    @botcmd(split_args_with=' ')
    def elo_add(self, mess, args):
        """
        Add a player
        """
        if len(args) != 1:
            return 'Just name a player'
        player = args[0]
        if player in self.get_players():
            return 'this player already exists'
        self.add_players(player)
        self.shelf.sync()
        return 'Player %s added' % player


    @botcmd(split_args_with=' ')
    def elo_remove(self, mess, args):
        """
        Remove a player
        """
        if len(args) != 1:
            return 'Just name a player'
        player = args[0]
        if player not in self.get_players():
            return 'this player doesn\'t exist...'
        self.remove_players(player)
        self.shelf.sync()
        return 'Player %s removed' % player


    @botcmd(split_args_with=' ')
    def elo_match(self, mess, args):
        """
        record a match result
        Syntax : !elo match player1 player2 player2 with player = winner
        """
        if len(args) != 3:
            return 'Syntax : !elo match player1 player2 player2 with player2 = winner'

        players = self.get_players()
        for player in args:
            if player not in players:
                return 'Unknown player %s' % player
        p1 = args[0]
        p2 = args[1]
        if p1 == p2:
            return 'Really?... Sorry.. Can\'t play against yourself (dah...).'
        winner = args[2]
        if winner != p1 and winner != p2:
            return 'The winner of the match did not play ?!'
        looser = p1 if winner == p2 else p2
        (winner_oldrank, winner_rank), (looser_oldrank, looser_rank) = self.add_game_result(winner, looser)
        return 'Game added %s won against %s.\n%10s %4i -> %4i\n%10s %4i -> %4i' % (winner, looser, winner, winner_oldrank, winner_rank, looser, looser_oldrank, looser_rank)

    @botcmd
    def elo_stats(self, mess, args):
        stats = {}
        logging.info("%s"%self['games_record'])
        for winner, looser, d in self['games_record']:
            if stats.has_key(winner):
                stats[winner]['wins'] += 1
                stats[winner]['last_game'] = d
            else:
                stats[winner] = {'wins': 1, 'losses': 0, 'first_game': d, 'last_game': d}

            if stats.has_key(looser):
                stats[looser]['losses'] += 1
                stats[looser]['last_game'] = d
            else:
                stats[looser] = {'wins': 0, 'losses': 1, 'first_game': d, 'last_game': d}
        results = stats.items()
        results= sorted(results, key=lambda result: result[1]['losses']-result[1]['wins'])
        return '    Player        wins      losses          first/last\n' + '\n'.join( ["%10s  %10i %10i           [%s/%s]" % (result[0],result[1]['wins'],result[1]['losses'], result[1]['first_game'], result[1]['last_game']) for result in results ] )


    @botcmd
    def elo_rankings(self, mess, args):
        """ Printout the current elo rankings
        """
        l = [(rank, player) for player, rank in self.get_players().iteritems()]
        l.sort(reverse=True)
        return '\n'.join(['%02i - %9s [%4i]' % (i+1, player, rank) for (i, (rank, player)) in enumerate(l)])

    @botcmd
    def elim_cancel(self, mess, args):
        """ Cancel the current direct elimination tournament
        """
        self['round'] = None
        return 'Tournament cancelled'

    def elim_pairings(self, players):
        players.sort(reversed=True)

        head = 1
        tail = len(players) - 2

        while head < tail:
            swapped = players[head]
            players[head] = players[tail]
            players[tail] = swapped
            head += 2
            tail += 2
        return zip(players[0::2], players[1::2])

    def get_matches_to_play(self):
        round = self['round']
        for layer in range(0, len(round) - 1):
            for match_index in range(0, len(round[layer])):
                pass ###################

    @botcmd(split_args_with=' ')
    def elim_start(self, mess, args):
        """ Start a direct elimination tournament amongst the players
        optionally give as parameter all the players participating to it
        """
        round = self.get('round', None)
        if round is not None:
            return 'Sorry a tournament is already going, use !swiss cancel to cancel it'
        if len(args) < 4:
            return 'There are less than 4 people, what is the point of this tournament ?'
        players = self.get_players()
        selected_players = []
        for player in args:
            if player not in players:
                return 'Unknown player %s' % player
            selected_players.append((players[player], player)) # add the tuple rank + name

        nb_players = len(selected_players)
        selected_players.extend([(0, 'bye')] * (2 ** ceil(sqrt(nb_players)) - nb_players))

        round = [self.elim_pairings(selected_players)]

        while len(round[-1]) != 1:
            round.append([None] * (len(round[-1]) / 2))
        self['round'] = round

        return '\n'.join(['%10s vs %10s' % (p1, p2) for (p1, p2) in self['round'][0]])

