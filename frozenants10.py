#!/usr/bin/env python

from ants import *
import random
from random import randint
import csv
from collections import namedtuple, deque, defaultdict
from math import sqrt
from bisect import insort

path_node = namedtuple('loc_node', ['parent', 'location'])
frontier_node = namedtuple('frontier_node', ['h_val', 'f_val', 'location', 'parent'])
stored_MDP = namedtuple('stored_MDP', ['frontier_lst', 'visited_set', 'cost_val'])

random.seed()

logs = csv.writer(open('log_frozenants.csv', 'wb'))

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
        self.area = ants.cols * ants.rows
        self.translator = [[(row, col) for col in range(ants.cols)] for row in range(ants.rows)]

        self.hills = set() 
        self.unseen = set() 
        self.impassable = set()

        self.MDPs = []
        self.stored_MDPs = {} 
        self.global_gradient = defaultdict(int)
        self.hill_MDP_frontier = [] 

        self.stored_paths = {}
        self.path_dists = {}

        self.food_locs = []
        self.explore_locs = set()
        self.bookkeeping = []

        for row in range(0, ants.rows):
            for col in range(0, ants.cols):
                self.unseen.add((row, col))

    def do_turn(self, ants):
        # loop through all my ants and try to give them orders
        # the ant_loc is an ant location tuple in (row, col) form
        destination = ants.destination
        direction = ants.direction
        distance = ants.distance
        visible = ants.visible
        passable = ants.passable
        unoccupied = ants.unoccupied
        time_remaining = ants.time_remaining

        orders = {}
        available_ants = set(ants.my_ants())

        def do_move_direction(loc, direction):
            new_loc = destination(loc, direction)
            if new_loc not in orders and new_loc not in self.impassable:
                ants.issue_order((loc, direction))
                orders[new_loc] = loc
                return True
            else:
                return False

        def do_move_location(loc, dest):
            if loc == dest or loc not in available_ants:
                return False
            directions = direction(loc, dest)
            for dir in directions:
                if do_move_direction(loc, dir):
                    available_ants.remove(loc)
                    return True
            return False

        def get_adjacent(loc):
            return [destination(loc, dir) for dir in ('n', 'e', 's', 'w')]

        enemy_ants = set([loc for loc, owner in ants.enemy_ants()])
        enemy_hills = set([loc for loc, owner in ants.enemy_hills()])

        food_dists = []
        food_locs = set(ants.food())
        hill_dists = []
        explore_dists = []
        ant_proximity = {}
        enemy_proximity = {}
        def update_visible():
            ' determine which squares are visible to the given player '
            if not hasattr(ants, 'vision_offsets_2'):
                # precalculate squares around an ant to set as visible
                ants.vision_offsets_2 = []
                mx = int(sqrt(ants.viewradius2))
                for d_row in range(-mx, mx + 1):
                    for d_col in range(-mx, mx + 1):
                        d = d_row**2 + d_col**2
                        if d <= ants.viewradius2:
                            ants.vision_offsets_2.append((
                                # Create all negative offsets so vision will
                                # wrap around the edges properly
                                (d_row % ants.rows) - ants.rows,
                                (d_col % ants.cols) - ants.cols
                                ))
                            # set all spaces as not visible
            # loop through ants and set all squares around ant as visible
            ants.vision = [[False]*ants.cols for row in range(ants.rows)]
            for ant in ants.my_ants():
                a_row, a_col = ant
                ant_proximity[ant] = []
                enemy_proximity[ant] = []
                if ant in self.explore_locs:
                    self.explore_locs.remove(ant)
                for v_row, v_col in ants.vision_offsets_2:
                    ants.vision[a_row + v_row][a_col + v_col] = True
                    explore_loc = self.translator[a_row + v_row][a_col + v_col] 
                    if explore_loc in self.unseen:
                        self.unseen.remove(explore_loc)
                        if not passable(explore_loc):
                            self.impassable.add(explore_loc)
                        elif explore_loc in enemy_hills: 
                            self.hills.add(explore_loc)
                        else:
                            # explore locs are places to explore. 1 is added on average every 4x4 area.
                            if randint(0, 15) == 2: 
                                self.explore_locs.add(explore_loc)
                    if explore_loc in food_locs:
                        insort(food_dists, (fdistance(ant, explore_loc), ant, explore_loc))
                    elif explore_loc in self.hills:
                        # the hills is still there, store the distance to it
                        if explore_loc in enemy_hills:
                            insort(hill_dists, (fdistance(ant, explore_loc), ant, explore_loc))
                        # else the hill has been razed, remove it
                        else:
                            self.hills.remove(explore_loc)
                    elif explore_loc in self.explore_locs:
                        insort(explore_dists, (fdistance(ant, explore_loc), ant, explore_loc))
                    elif explore_loc in available_ants:
                        insort(ant_proximity[ant], (fdistance(ant, explore_loc), ant, explore_loc))
                    elif explore_loc in enemy_ants: 
                        insort(enemy_proximity[ant], (fdistance(ant, explore_loc), explore_loc))

            return 
    
        def find_path(start_loc, dest, threshold):
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
            visited = set() 
            # initialize variables
            f = 0 
            loc = start_loc
            par = None
            # loc is the current tile being examined.
            # each loop iteration examines the frontier tile with lowest h value.
            while loc != dest and (loc, dest) not in self.stored_paths: 
                this_path_node = path_node(parent=par, location=loc)
                # expand the frontier by adding adjacent locations
                # if the location isn't passable or has already been visited, skip 
                for adj_loc in filter(lambda l: l not in visited and l not in self.impassable, 
                                      [destination(loc, dir) for dir in ('n', 'e', 's', 'w')]):
                    # set f' and g'
                    fp = f + 1 
                    gp = int(distance(adj_loc, dest)*0.9)
                    # add to frontier and visited
                    insort(frontier, frontier_node(h_val=fp + gp, f_val=fp, location=adj_loc, parent=this_path_node))
                    visited.add(adj_loc)
                # dead end. This occurs when there is no visible path to dest
                frontier_len = len(frontier)
                if frontier_len == 0:
                    return start_loc 
                if f*threshold > time_remaining():
                    return start_loc
                # sort frontier, so the node with lowest h is at the front
                # pop off node with the lowest h value for next iteration
                h, f, loc, par = frontier.pop(0)
            # prev is the previous location's parent
            if (loc, dest) in self.path_dists:
                path_dist_offset = self.path_dists[(loc, dest)] 
            else:
                path_dist_offset = 0
            final_path = []
            # loop retraces back to start_loc, ends when it finds the node with no parent
            while par != None:
                # if part of the path is unknown, it could potentially be a bad path
                if not visible(loc):
                    memoization = False
                final_path.insert(0, loc)
                next_par, loc = par
                par = next_par
            step = start_loc
            dist = len(final_path) + path_dist_offset
            reverse_dist = 0
            for next_step in final_path:
                self.path_dists[(step, dest)] = dist - reverse_dist
                self.path_dists[(dest, step)] = reverse_dist 
                reverse_dist += 1
                step = next_step
            if memoization:
                step = start_loc
                for next_step in final_path:
                    self.stored_paths[(step, dest)] = next_step
                    self.stored_paths[(dest, next_step)] = step
                    step = next_step
            if (start_loc, dest) in self.stored_paths:
                return self.stored_paths[(start_loc, dest)]
            else:
                return final_path[0]

        def fdistance(start_loc, dest):
            if start_loc == dest:
                return 0
            elif (start_loc, dest) not in self.path_dists:
                return distance(start_loc, dest)
            else:
                return self.path_dists[(start_loc, dest)]

        def hill_MDP(start_loc):
            if start_loc not in self.stored_MDPs: 
                self.stored_MDPs[start_loc] = stored_MDP(frontier_lst=[(1, start_loc)], visited_set=set([start_loc]), cost_val=-2)
                self.unseen.remove(start_loc)
                self.impassable.remove(start_loc)
            frontier, visited, cost = self.stored_MDPs[start_loc]
            next_turn_frontier = [] 
            while len(frontier) > 0:
                value, frontier_loc = frontier.pop(0) 
                next_value = value - cost
                for adj_loc in [destination(loc, dir) for dir in ('n', 'e', 's', 'w')]:
                    # if adj_loc has already been visited and a lower gradient than the current value, then 
                    # we already have the most direct route. 
                    # If it has a higher gradient than current, then we have found a more direct route to the tile,
                    # so explore it again.
                    if adj_loc in visited:
                    #    if self.global_gradient[adj_loc] <= next_value:
                            continue
                    #    else:
                    #        pass
                    # adj_loc has not been visited, but it is visible. Uncharted territory, chart it.
                    elif visible(adj_loc):
                        self.unseen.remove(adj_loc)
                        if passable(adj_loc):
                            self.impassable.remove(adj_loc)
                        # if adj_loc is impassable, add it to visited, but not to the frontier.
                        else:
                            self.global_gradient[adj_loc] = -100
                            visited.add(adj_loc)
                            continue
                    # else, adj_loc has not been visited and is not visible. Since frontier_loc could have children
                    # that cannot be accessed, it has to be re-added to frontier. Leave adj_loc alone.
                    else:
                        insort(next_turn_frontier, (value, frontier_loc))
                        continue
                    # If we reach this point, we know adj_loc needs to be added to the frontier.
                    insort(frontier, (next_value, adj_loc))
                    visited.add(adj_loc)
                    self.global_gradient[adj_loc] = next_value
                    if time_remaining() < 250:
                        break
            self.stored_MDPs[start_loc] = stored_MDP(frontier_lst=next_turn_frontier, visited_set=visited, cost_val=cost)
            self.hill_MDP_frontier = next_turn_frontier
            return

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
                    if time_remaining() < 50:
                        return
                    if len(frontier) == 0: 
                        break
                    locp, Q, cost = frontier.pop(0)
                    if Q == 0:
                        break
                    local_MDP.append((locp, Q))
                    for direction in directions:
                        dest = destination(locp, direction)
                        if dest not in visited and dest not in [l for l, q, c in frontier] and passable(dest):
                            frontier.append((dest, Q + cost, cost + cost_increment))
                    visited.append(locp)
                self.stored_MDPs[(loc, type)] = local_MDP[:]
            for loc, Q in local_MDP:
                row, col = loc
                self.MDPs[row][col] += Q
            return

        # end function definitions

        update_visible()
        new_bookkeeping = []

        # Prevent stepping on own hill
        for hill_loc in ants.my_hills():
            orders[hill_loc] = None

        for dist, ant_loc, hill_loc in hill_dists:
            if time_remaining() < 10:
                break
            if ant_loc not in available_ants:
                continue
            dest = find_path(ant_loc, hill_loc, 5)
            do_move_location(ant_loc, dest)
            if (dest, hill_loc) in self.stored_paths:
                new_bookkeeping.append(('hill', dest, hill_loc))

        food_targets = set() 
        # find close food
        for dist, ant_loc, food_loc in food_dists:
            if time_remaining() < 10:
                break
            if ant_loc not in available_ants:
                continue
            if food_loc not in food_targets:
                food_targets.add(food_loc)
                dest = find_path(ant_loc, food_loc, 12)
                do_move_location(ant_loc, dest)
                if (dest, food_loc) in self.stored_paths:
                    new_bookkeeping.append(('food', dest, food_loc))

        explore_targets = set()
        for type, ant_loc, target_loc in self.bookkeeping:
            if time_remaining() < 10:
                break
            if ant_loc not in available_ants:
                continue
            if (ant_loc, target_loc) not in self.stored_paths:
                continue
            if type == 'hill':
                if target_loc not in self.hills:
                    continue
                else:
                    dest = self.stored_paths[(ant_loc, target_loc)]
                    do_move_location(ant_loc, dest)
                    if dest != target_loc:
                        new_bookkeeping.append(('hill', dest, target_loc))
            elif type == 'explore':
                dest = self.stored_paths[(ant_loc, target_loc)]
                do_move_location(ant_loc, dest)
                explore_targets.add(target_loc)
                if dest != target_loc:
                    new_bookkeeping.append(('explore', dest, target_loc))
            elif type == 'food':
                if target_loc in food_targets:
                    continue
                else:
                    dest = self.stored_paths[(ant_loc, target_loc)]
                    do_move_location(ant_loc, dest)
                    food_targets.add(target_loc)
                    if dest != target_loc:
                        new_bookkeeping.append(('food', dest, target_loc))
        self.bookkeeping = new_bookkeeping

        # explore the map
        if time_remaining() > 50:
            for dist, ant_loc, explore_loc in explore_dists:
                if time_remaining() < 10:
                    break
                if ant_loc not in available_ants or explore_loc in explore_targets:
                    continue
                else:
                    dest = find_path(ant_loc, explore_loc, 10)
                    do_move_location(ant_loc, dest)
                    if (dest, explore_loc) in self.stored_paths:
                        self.bookkeeping.append(('explore', dest, explore_loc))
        
        if time_remaining() > 50:
            dists = []
            for ant in list(available_ants):
                if time_remaining() < 50:
                    break
                dists = [(fdistance(ant, hill_loc), hill_loc) for hill_loc in self.hills]
                dists.sort()
                for dist, hill_loc in dists:
                    if time_remaining < 10:
                        break
                    dest = find_path(ant, hill_loc, 3)
                    if do_move_location(ant, dest):
                        if (dest, hill_loc) in self.stored_paths:
                            self.bookkeeping.append(('hill', dest, hill_loc))
                        break

        if ants.time_remaining() > 50:
            dists = []
            for ant in list(available_ants):
               if ants.time_remaining() < 50:
                    break
               dists = [(fdistance(ant, explore_loc), explore_loc) 
                         for explore_loc in self.explore_locs if explore_loc not in explore_targets]
               dists.sort()
               for dist, explore_loc in dists:
                   if ants.time_remaining() < 10:
                        break
                   dest = find_path(ant, explore_loc, 3)
                   if do_move_location(ant, dest):
                       if (dest, explore_loc) in self.stored_paths:
                           self.bookkeeping.append(('explore', dest, explore_loc))
                       break

        for ant in available_ants:
            for dir in ('n', 'e', 's', 'w'):
                if do_move_direction(ant, dir): 
                    break

        # Unblock own hill
        for hill_loc in ants.my_hills():
            if hill_loc in available_ants: 
                for direction in ('s', 'e', 'w', 'n'):
                    if do_move_direction(hill_loc, direction):
                        break



if __name__ == '__main__':
    # psyco will speed up python a little, but is not needed
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    try:
        # if run is passed a class with a do_turn method, it will do the work
        # this is not needed, in which case you will need to write your own
        # parsing function and your own game state class
        Ants.run(MyBot())
    except KeyboardInterrupt:
        print('ctrl-c, leaving ...')
