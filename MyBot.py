#!/usr/bin/env python
from ants import *
import csv

# define a class with a do_turn method
# the Ants.run method will parse and update bot input
# it will also run the do_turn method for us
class ant:
    def __init__(self, loc, unseen, passable, orders):
        self.loc = loc
        self.state = 'exploring'
        self.path = []
        self.unseen = unseen
        self.passable = passable
        self.orders = orders
    def move(self, dest):
        pass

    def calculate_path(self, dest):
        self.path = []
        shortest_dist = self.ants.distance(self.loc, dest)	
        visited = [(self.loc, self.loc)]
        # Frontier is stored as a tupple of (h, f, g (A* meanings), loc, parent)
        frontier = []
        directions = ['n', 'e', 's', 'w']
        # Special case for first move
        h, f, g, next_loc = shortest_dist, 0, shortest_dist, self.loc
        for direction in directions:
            explore = ants.destination(self.loc, direction)
            if explore in ants.unoccupied() and not explore in self.orders:
                new_f, new_g = f + 1, ants.distance(self.loc, explore)
                frontier.append((new_f + new_g, new_f, new_g, explore, self.loc))
            else:
                pass
        if len(frontier) == 0:
            self.orders[self.loc] = self.loc
            return self.loc
        frontier.sort()
        while(True):
            h, f, g, next_loc, next_parent = frontier.pop(0)
            if next_loc == dest:
                break
            visited.append((next_loc, next_parent))
            for direction in directions:
                explore = ants.destination(next_loc, direction)
                if not explore in visited and (ants.passable(explore) or explore in self.unseen): 
                    new_f, new_g = f + 1, ants.distance(self.loc, explore)
                    frontier.append((new_f + new_g, new_f, new_g, explore, next_loc))
                else:
                    pass
            frontier.sort()
        self.path = [dest]
        for next_loc, par in visited.reverse():
            if next_loc == next_parent:
                self.path.insert(0, next_loc)
                next_parent = par
        return self.path[1]


    def update_position(self, ants, orders):
        pass

class MyBot:
    def __init__(self):
        # define class level variables, will be remembered between turns
        pass

    # do_setup is run once at the start of the game
    # after the bot has received the game settings
    # the ants class is created and setup by the Ants.run method
    def do_setup(self, ants):
        self.recorder = csv.writer(open('MyBot.csv', 'wb'))
        self.hills = []
        self.unseen = []
        self.passable = []
        self.ants = []
        for row in range(ants.rows):
            for col in range(ants.cols):
                self.unseen.append((row, col))

    # do turn is run once per turn
    # the ants class has the game state and is updated by the Ants.run method
    # it also has several helper methods to use
    def do_turn(self, ants):
        # track all moves, prevent collisions
        orders = {}
        def do_move_direction(loc, direction):
            new_loc = ants.destination(loc, direction)
            if (ants.unoccupied(new_loc) and new_loc not in orders):
                ants.issue_order((loc, direction))
                orders[new_loc] = loc
                return True
            else:
                return False

        targets = {}
        def do_move_location(loc, dest):
            directions = ants.direction(loc, dest)
            for direction in directions:
                if do_move_direction(loc, direction):
                    targets[dest] = loc
                    return True
            alternatives = [dir for dir in ['n', 'e', 's', 'w'] if dir not in directions]
            for direction in alternatives:
                if do_move_direction(loc, direction):
                    targets[dest] = loc
                    return True

        def passable_or_doubt(loc):
            if passable(loc) or loc in self.unseen:
                return True
            else:
                return False

        # unblock own hill
        for hill_loc in ants.my_hills():
            if hill_loc in ants.my_ants():
                self.ants.append(ant(hill_loc, self.unseen, self.passable, self.orders))

        # prevent stepping on own hill
        for hill_loc in ants.my_hills():
            orders[hill_loc] = None

        # food gathering
        ant_dist = []
        for food_loc in ants.food():
            for ant_loc in ants.my_ants():
                dist = ants.distance(ant_loc, food_loc)
                ant_dist.append((dist, ant_loc, food_loc))
        ant_dist.sort()
        for dist, ant_loc, food_loc in ant_dist:
            if food_loc not in targets and ant_loc not in targets.values():
                do_move_location(ant_loc, food_loc)

        # attack enemy hill
        for hill_loc, hill_owner in ants.enemy_hills():
            if hill_loc not in self.hills:
                self.hills.append(hill_loc)
        ant_dist = []
        for hill_loc in self.hills:
            for ant_loc in ants.my_ants():
                if ant_loc not in orders.values():
                    dist = ants.distance(ant_loc, hill_loc)
                    ant_dist.append((dist, ant_loc, hill_loc))
        ant_dist.sort()
        for dist, ant_loc, hill_loc in ant_dist:
            do_move_location(ant_loc, hill_loc)


        # explore unseen areas
        for loc in self.unseen[:]:
            if ants.visible(loc):
                self.unseen.remove(loc)
        for ant_loc in ants.my_ants():
            if ant_loc not in orders.values():
                unseen_dist = []
                for unseen_loc in self.unseen:
                    dist = ants.distance(ant_loc, unseen_loc)
                    unseen_dist.append((dist, unseen_loc))
                unseen_dist.sort()
                for dist, unseen_loc in unseen_dist:
                    if do_move_location(ant_loc, unseen_loc): 
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
