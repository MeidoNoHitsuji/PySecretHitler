from enum import Enum
import random
from typing import List

from secret_hitler.exceptions import GameError
from secret_hitler.player import Player, Identity

class DuplicatePlayerNameError(GameError):
    def __init__(self, dup_name):
        self.dup_name = dup_name
        super().__init__(f"Duplicate name not allowed: {dup_name}")

class NonexistentPlayerNameError(GameError):
    def __init__(self, player_name):
        self.player_name = player_name
        super().__init__(f"Nonexistent player used: {player_name}")

class NonexistentTileError(GameError):
    def __init__(self, tile):
        self.tile = tile
        super().__init__(f"Cannot discard non-existent tile: {tile}")

class InvalidNumPlayersError(GameError):
    def __init__(self, num_players):
        self.num_players = num_players
        super().__init__(f"Invalid number of players {num_players}. Min: 5, Max 10.")

class Tile(Enum):
    LIBERAL_POLICY = 0
    FASCIST_POLICY = 1

    def __str__(self):
        if self.value == 0:
            return "Liberal"
        return "Fascist"

class PresidentialPower(Enum):
    INVESTIGATE_LOYALTY = 0
    CALL_SPECIAL_ELECTION = 1
    POLICY_PEEK = 2
    EXECUTION = 3

# num_players -> num_liberals, num_fascists, presidential_powers
NUM_PLAYERS_TO_BOARD_CONFIG = {
    5: (3,1,
        [None,
         None,
         PresidentialPower.POLICY_PEEK,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None]),
    6: (4,1,
        [None,
         None,
         PresidentialPower.POLICY_PEEK,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None]),
    7: (4,2,
        [None,
         PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.CALL_SPECIAL_ELECTION,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None]),
    8: (5,2,
        [None,
         PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.CALL_SPECIAL_ELECTION,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None]),
    9: (5,3,
        [PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.CALL_SPECIAL_ELECTION,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None]),
    10: (6,3,
        [PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.INVESTIGATE_LOYALTY,
         PresidentialPower.CALL_SPECIAL_ELECTION,
         PresidentialPower.EXECUTION,
         PresidentialPower.EXECUTION,
         None])
}

LIBERAL_WINNING_PROGRESS = 5
FASCIST_WINNING_PROGRESS = 6

class Board:
    def __init__(self):
        self.players : List[Player] = []              # active players only
        self.eliminated_players : List[Player] = []
        self.president_id : int = 0
        self.chancellor : Player = None
        self.prev_president : Player = None
        self.prev_chancellor : Player = None
        self.nominated_chancellor : Player = None
        self.unused_tiles : List[Tile] = [Tile.LIBERAL_POLICY] * 6 + [Tile.FASCIST_POLICY] * 11
        self.discarded_tiles : List[Tile] = []
        self.drawn_tiles : List[Tile] = []
        self.latest_policy : Tile = None
        self.liberal_progress : int = 0
        self.fascist_progress : int = 0
        self.fascist_powers: List[PresidentialPower] = None
        
        # keeps track of updated properties
        self.updates = set()

        random.shuffle(self.unused_tiles)
    
    private_state_translations = {
        "players": (lambda me,l: [p.name for p in l]),
        "eliminated_players": (lambda me,l: [p.name for p in l]),
        "president": (lambda me,id: me.players[id]),
        "chancellor": None,
        "nominated_chancellor": None,
        "unused_tiles": (lambda me,l: len(l)),
        "discarded_tiles": (lambda me,l: len(l)),
        "drawn_tiles": (lambda me,l: [str(t) for t in l]),
        "liberal_progress": None,
        "fascist_progress": None,
    }
    
    def register_update(self, prop):
        self.updates.add(prop)

    def extract_updates(self, custom_updates=None):
        new_updates = custom_updates or self.updates
        response = dict()
        for prop in new_updates:
            if private_state_translations[prop] is not None:
                response[prop] = getattr(self, prop)
            else:
                response[prop] = private_state_translations[prop](self, getattr(self, prop))
        self.updates = set()
        return response

    def get_full_state(self):
        return self.extract_updates(self, private_state_translations.keys())
    
    def add_player(self, name: str):
        self.register_update("players")
        if any(p.name == name for p in self.players):
            raise DuplicatePlayerNameError(name)
        self.players.append(Player(len(self.players), name))
    
    def get_player(self, name: str):
        for p in self.players:
            if p.name == name:
                return p
        raise NonexistentPlayerNameError(name)
    
    def begin_game(self):
        self.register_update("players")
        self.register_update("fascist_powers")
        if len(self.players) not in NUM_PLAYERS_TO_BOARD_CONFIG:
            raise InvalidNumPlayersError(len(self.players))
        
        board_config = NUM_PLAYERS_TO_BOARD_CONFIG[len(self.players)]
        identities = ([Identity.LIBERAL] * board_config[0]
                      + [Identity.FASCIST] * board_config[1]
                      + [Identity.HITLER])
        random.shuffle(identities)

        for i in range(len(self.players)):
            self.players[i].identity = identities[i]
        
        self.fascist_powers = board_config[2]
    
    def get_president(self):
        return self.players[self.president_id]
    
    def advance_president(self):
        self.register_update("president_id")
        self.prev_president = self.get_president()
        self.president_id = (president_id + 1) % len(self.players)

    def draw_three_tiles(self):
        if len(self.unused_tiles) < 3:
            # shuffle discarded tiles and put under unused tiles
            random.shuffle(self.discarded_tiles)
            self.unused_tiles += self.discarded_tiles
            self.discarded_tiles = []
            self.register_update("unused_tiles")
            self.register_update("discarded_tiles")
        
        self.drawn_tiles = self.unused_tiles[:3]
        self.unused_tiles = self.unused_tiles[3:]
        self.register_update("drawn_tiles")
        self.register_update("unused_tiles")

    def discard_tile(self, tile: Tile):
        if tile not in self.drawn_tiles:
            raise NonexistentTileError(tile)
        self.drawn_tiles.remove(tile)
        self.discarded_tiles.append(tile)
        self.register_update("drawn_tiles")
        self.register_update("discarded_tiles")

        if len(self.drawn_tiles) == 1:
            # enact policy
            self.latest_policy = self.drawn_tiles[0]
            if self.latest_policy == Tile.LIBERAL_POLICY:
                self.liberal_progress += 1
            if self.latest_policy == Tile.FASCIST_POLICY:
                self.fascist_progress += 1
            # destroy enacted tile (do not put back into any tile list)
            self.drawn_tiles = []
            self.register_update("drawn_tiles")
    
    def get_winner(self):
        if self.liberal_progress == LIBERAL_WINNING_PROGRESS:
            return Tile.LIBERAL_POLICY
        if self.fascist_progress == FASCIST_WINNING_PROGRESS:
            return Tile.FASCIST_POLICY
        return None

    def get_current_presidential_power(self):
        if self.latest_policy != Tile.FASCIST_POLICY:
            return None
        if self.fascist_progress == 0:
            return None
        return self.fascist_powers[self.fascist_progress - 1]
