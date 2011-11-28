#!/usr/bin/env python

import random
from random import randint
import csv
from collections import namedtuple, deque
from math import sqrt

path_node = namedtuple('loc_node', ['parent', 'location'])
frontier_node = namedtuple('frontier_node', ['h_val', 'f_val', 'location', 'parent'])

random.seed()

logs = csv.writer(open('log_frozenants.csv', 'wb'))

MY_ANT = 0
ANTS = 0
DEAD = -1
LAND = -2
FOOD = -3
WATER = -4

PLAYER_ANT = 'abcdefghi'
HILL_ANT = string = 'ABCDEFGHI'
PLAYER_HILL = string = '0123456789'
MAP_OBJECT = '?%*.!'
MAP_RENDER = PLAYER_ANT + HILL_ANT + PLAYER_HILL + MAP_OBJECT

AIM = {'n': (-1, 0),
        'e': (0, 1),
        's': (1, 0),
        'w': (0, -1)}
RIGHT = {'n': 'e',
        'e': 's',
        's': 'w',
        'w': 'n'}
LEFT = {'n': 'w',
        'e': 'n',
        's': 'e',
        'w': 's'}
BEHIND = {'n': 's',
        's': 'n',
        'e': 'w',
        'w': 'e'}
TYPE = {'food': (130, -5),
        'fog' : (20, -2),
        'hill': (150, -5)}

def get_adjacent(ants, loc):
    return [ants.destination(loc, dir) for dir in ('n', 'e', 's', 'w')]

def get_adjacent2(ants, loc):
    return [ants.destination(ants.destination(loc, dir), dir) for dir in ('n', 'e', 's', 'w')]

straight_paths = {}
def straight_path(ants, start_loc, dest):
    loc = start_loc
    path = []
    while (loc != dest and ants.time_remaining() > 50):
        path.append(loc)
        if (loc, dest) in straight_paths:
            is_passable = straight_paths[(loc, dest)]
            loc = dest
        else:
            directions = ants.direction(loc, dest)
            is_passable = False
            for direction in directions:
                next_loc = ants.destination(loc, direction)
                if ants.passable(next_loc):
                    loc = next_loc
                    is_passable = True
                    break
        for step in path:
            straight_paths[(step, loc)] = is_passable
            straight_paths[(loc, step)] = is_passable
        if not is_passable: 
            return False
    return True


class MyBot:
    def __init__(self):
        # define class level variables, will be remembered between turns
        pass

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants):
        # initialize data structures after learning the game settings
        self.hills = []
        self.unseen = []
        self.explore_locs = ants.my_hills() 
        self.explored = []
        self.impassable = []
        self.MDPs = []
        self.stored_MDPs = {}
        self.stored_paths = {}
        self.path_dists = {}
        self.food_locs = []
        self.bookkeeping = []
        self.rallypoint = False
        for row in range(0, ants.rows):
            for col in range(0, ants.cols):
                self.unseen.append((row, col))

    def do_turn(self, ants):
        # loop through all my ants and try to give them orders
        # the ant_loc is an ant location tuple in (row, col) form
        orders = {}
        def do_move_direction(loc, direction):
            new_loc = ants.destination(loc, direction)
            if (ants.unoccupied(new_loc) and new_loc not in orders.keys()):
                ants.issue_order((loc, direction))
                orders[new_loc] = loc
                return True
            else:
                return False

        targets = {}
        def do_move_location(loc, dest):
            if loc == dest:
                return False
            if loc in orders.values():
                return False
            directions = ants.direction(loc, dest)
            for direction in directions:
                if do_move_direction(loc, direction):
                    targets[dest] = loc
                    available_ants.remove(loc)
                    return True
            return False

        def find_path(start_loc, dest):
            # A* is based on the heuristic h = f + g,
            # where f = distance traveled so far and g = straightline distance to dest.
            # fp and gp stand for 'f prime' and 'g prime'
            if start_loc == dest:
                return start_loc
            memoization = True
            # frontier stores nodes which haven't yet been expanded.
            # nodes are in form (h, f, location, parent)
            frontier = []
            # visited is simply a list of all explored locations
            visited = []
            # path list of explored locations in the form (location, parent)
            # for the purpose of retracing our steps once a solution has been reached 
            path = []
            # initialize variables
            h = 0
            f = ants.distance(start_loc, dest)
            loc = start_loc
            par = None
            # loc is the current tile being examined.
            # each loop iteration examines the frontier tile with lowest h value.
            while loc != dest and (loc, dest) not in self.stored_paths: 
                # path is used to retrace back to start_loc once we've found dest
                this_path_node = path_node(parent=par, location=loc)
                path.append(this_path_node)
                # expand the frontier by adding adjacent locations
                for adj_loc in get_adjacent(ants, loc):
                    # if the location isn't passable or has already been visited, skip 
                    if adj_loc in visited or adj_loc in self.impassable:# or not ants.visible(adj_loc):
                        continue
                    else:
                        # set f' and g'
                        fp = f + 1 
                        gp = ants.distance(adj_loc, dest)
                        # add to frontier and visited
                        frontier.append(frontier_node(h_val=fp + gp, f_val=fp, location=adj_loc, parent=this_path_node))
                        visited.append(adj_loc)
                # dead end. This occurs when there is no visible path to dest
                frontier_len = len(frontier)
                if frontier_len == 0:
                    return start_loc 
                if frontier_len*5 > ants.time_remaining():
                    return start_loc
                # sort frontier, so the node with lowest h is at the front
                frontier.sort()
                # pop off node with the lowest h value for next iteration
                h, f, loc, par = frontier.pop(0)
            # prev is the previous location's parent
            if (loc, dest) in self.stored_paths:
                path_dist_offset = self.path_dists[(loc, dest)] 
            else:
                path_dist_offset = 0
            final_path = []
            # loop retraces back to start_loc, ends when it finds the node with no parent
            while par != None:
                # if part of the path is unknown, it could potentially be a bad path
                if loc in self.unseen:
                    memoization = False
                final_path.insert(0, loc)
                next_par, loc = par
                par = next_par
            if memoization:
                step = start_loc
                dist = len(final_path) + path_dist_offset
                for next_step in final_path:
                    self.path_dists[(step, dest)] = dist
                    self.path_dists[(step, dest)] = dist
                    dist -= 1
                    self.stored_paths[(step, dest)] = next_step
                    step = next_step
            if (start_loc, dest) in self.stored_paths:
                return self.stored_paths[(start_loc, dest)]
            else:
                return final_path[0]

        def fdistance(start_loc, dest):
            if (start_loc, dest) in self.path_dists:
                return self.path_dists[(start_loc, dest)]
            else:
                return ants.distance(start_loc, dest)

        def MDP(loc, type):
            if (loc, type) in self.stored_MDPs:
                local_MDP = self.stored_MDPs[(loc, type)]
            else:
                Q, cost = TYPE[type]
                cost += randint(-2, 2)
                if cost > 0:
                    cost_increment = 1
                else:
                    cost_increment = -1
                directions = ('n', 'e', 's', 'w')
                frontier = [(loc, Q, cost)]
                visited = []
                local_MDP = []
                while(True):
                    if ants.time_remaining() < 50:
                        return
                    if len(frontier) == 0: 
                        break
                    locp, Q, cost = frontier.pop(0)
                    if Q == 0:
                        break
                    local_MDP.append((locp, Q))
                    for direction in directions:
                        dest = ants.destination(locp, direction)
                        if dest not in visited and dest not in [l for l, q, c in frontier] and ants.passable(dest):
                            frontier.append((dest, Q + cost, cost + cost_increment))
                    visited.append(locp)
                self.stored_MDPs[(loc, type)] = local_MDP[:]
            for loc, Q in local_MDP:
                row, col = loc
                self.MDPs[row][col] += Q
            return

        # end function definitions
        self.MDPs = [[0] * ants.cols for row in range(ants.rows)]
        available_ants = ants.my_ants()
        indexes = []
        for i, unseen_loc in enumerate(self.unseen):
            if ants.visible(unseen_loc):
                indexes.insert(0, i)
                if unseen_loc in self.explore_locs:
                    self.explore_locs.remove(unseen_loc)
                    row, col = unseen_loc
                    expanded_locs = ((row, (col + 10)), 
                            (row, (col - 10)), 
                            ((row + 10), col),
                            ((row - 10), col))
                    for expanded in expanded_locs: 
                        if 0 <= expanded[0] and expanded[0] < ants.rows and 0 <= expanded[1] and expanded[1] < ants.cols:
                            if expanded not in self.explored and expanded in self.unseen:
                                self.explore_locs.append(expanded)
                                self.explored.append(expanded)
                if not ants.passable(unseen_loc):
                    self.impassable.append(unseen_loc)
        for i in indexes:
            self.unseen.pop(i)

        # Prevent stepping on own hill
        for hill_loc in ants.my_hills():
            if hill_loc in ants.my_ants():
                orders[hill_loc] = None

        # update food_locs
        indexes = []
        for food_loc in ants.food():
            if food_loc not in self.food_locs:
                self.food_locs.append(food_loc)
        for i, food_loc in enumerate(self.food_locs):
            if ants.visible(food_loc) and food_loc not in ants.food():
                indexes.insert(0, i)
        for i in indexes:
            self.food_locs.pop(i)

        # update enemy hills
        for hill_loc, hill_owner in ants.enemy_hills():
            if hill_loc not in self.hills:
                self.hills.append(hill_loc)
        for hill_loc in self.hills:
            if hill_loc not in [loc for loc, owner in ants.enemy_hills()]:
                self.hills.remove(hill_loc)

        food_targets = [] 
        explore_targets = []
        new_bookkeeping = []
        while len(self.bookkeeping) > 0:
            type, ant_loc, target_loc = self.bookkeeping.pop()
            if ant_loc not in available_ants:
                continue
            if (ant_loc, target_loc) not in self.stored_paths:
                continue
            if type == 'food':
                if target_loc not in self.food_locs:
                    continue
                else:
                    food_targets.append(target_loc)
                    dest = self.stored_paths[(ant_loc, target_loc)]
                    do_move_location(ant_loc, dest)
                    if dest != target_loc:
                        new_bookkeeping.append(('food', dest, target_loc))
            if type == 'hill':
                if target_loc not in self.hills:
                    continue
                else:
                    dest = self.stored_paths[(ant_loc, target_loc)]
                    do_move_location(ant_loc, dest)
                    if dest != target_loc:
                        new_bookkeeping.append(('hill', dest, target_loc))

        self.bookkeeping = new_bookkeeping

        # find close food
        food_counter = 10 - len(ants.my_ants())//8
        if food_counter > 0:
            dists = []
            for food_loc in self.food_locs:
                if food_loc not in food_targets:
                    for ant_loc in available_ants: 
                        dist = fdistance(ant_loc, food_loc)
                        dists.append((dist, ant_loc, food_loc))
            dists.sort()
            for dist, ant_loc, food_loc in dists:
                if len(food_targets) > food_counter:
                    break
                if ant_loc not in available_ants:
                    continue
                if food_loc not in food_targets:
                    food_targets.append(food_loc)
                    dest = find_path(ant_loc, food_loc)
                    do_move_location(ant_loc, dest)
                    if dest != food_loc and (dest, food_loc) in self.stored_paths:
                        self.bookkeeping.append(('food', dest, food_loc))

        # attack hills
        if ants.time_remaining() > 140:
            dists = []
            for hill_loc in self.hills:
                for ant_loc in available_ants:
                    dist = fdistance(ant_loc, hill_loc)
                    dists.append((dist, ant_loc, hill_loc))
            dists.sort()
            for dist, ant_loc, hill_loc in dists:
                if ant_loc not in available_ants:
                    continue
                elif (ant_loc, hill_loc) in self.stored_paths:
                    dest = self.stored_paths[(ant_loc, hill_loc)] 
                    do_move_location(ant_loc, dest)
                    if (dest, hill_loc) in self.stored_paths:
                        self.bookkeeping.append(('hill', dest, hill_loc))
                elif ants.time_remaining() < dist*10:
                    break
                else: 
                    dest = find_path(ant_loc, hill_loc)
                    do_move_location(ant_loc, dest)
                    if (dest, hill_loc) in self.stored_paths:
                        self.bookkeeping.append(('hill', dest, hill_loc))

        # explore the map
        if ants.time_remaining() > 80:
            dists = []
            for explore_loc in self.explore_locs:
                for ant_loc in available_ants:
                    dist = fdistance(ant_loc, explore_loc)
                    dists.append((dist, ant_loc, explore_loc))
            dists.sort()
            for dist, ant_loc, explore_loc in dists:
                if ant_loc not in available_ants:
                    continue
                elif (ant_loc, explore_loc) in self.stored_paths:
                    do_move_location(ant_loc, self.stored_paths[(ant_loc, explore_loc)]) 
                elif ants.time_remaining() < dist*10:
                    break
                else:
                    dest = find_path(ant_loc, explore_loc)
                    do_move_location(ant_loc, dest)

        for ant_loc in available_ants:
            do_move_location(ant_loc, (randint(0, ants.rows), randint(0, ants.cols)))

        # Unblock own hill
        for hill_loc in ants.my_hills():
            if hill_loc in available_ants: 
                for direction in ('s', 'e', 'w', 'n'):
                    if do_move_direction(hill_loc, direction):
                        break
