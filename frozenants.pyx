#!/usr/bin/env python

import random
from random import randint
import csv

cdef extern from "math.h":
	double sqrt(double n)

random.seed()

MY_ANT = 0
ANTS = 0
DEAD = -1
LAND = -2
FOOD = -3
WATER = -4

PLAYER_ANT = 'abcdefghij'
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

def fdestination(ants, loc, direction):
	'calculate a new location given the direction and wrap correctly'
	cdef int row, col
	cdef int d_row, d_col
	row, col = loc
	d_row, d_col = AIM[direction]
	return ((row + d_row) % ants.rows, (col + d_col) % ants.cols)        

cdef int fdistance(ants, loc1, loc2):
	'calculate the closest distance between to locations'
	cdef int row1, col1, row2, col2, d_col, d_row
	row1, col1 = loc1
	row2, col2 = loc2
	d_col = min(abs(col1 - col2), ants.cols - abs(col1 - col2))
	d_row = min(abs(row1 - row2), ants.rows - abs(row1 - row2))
	return d_row + d_col

def fdirection(ants, loc1, loc2):
	'determine the 1 or 2 fastest (closest) directions to reach a location'
	cdef int row1, col1, row2, col2, height2, width2
	row1, col1 = loc1
	row2, col2 = loc2
	height2 = ants.rows//2
	width2 = ants.cols//2
	d = []
	if row1 < row2:
		if row2 - row1 >= height2:
			d.append('n')
		if row2 - row1 <= height2:
			d.append('s')
	if row2 < row1:
		if row1 - row2 >= height2:
			d.append('s')
		if row1 - row2 <= height2:
			d.append('n')
	if col1 < col2:
		if col2 - col1 >= width2:
			d.append('w')
		if col2 - col1 <= width2:
			d.append('e')
	if col2 < col1:
		if col1 - col2 >= width2:
			d.append('e')
		if col1 - col2 <= width2:
			d.append('w')
	return d

def get_all_visible(ants):
	' determine which squares are visible to the given player '
	cdef int mx
	cdef int a_row, a_col
	visible = []
	if ants.vision == None:
		if not hasattr(ants, 'vision_offsets_2'):
			# precalculate squares around an ant to set as visible
			ants.vision_offsets_2 = []
			mx = int(sqrt(ants.viewradius2))
			for d_row in range(-mx,mx+1):
				for d_col in range(-mx,mx+1):
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
	for ant in ants.my_ants():
		a_row, a_col = ant
		for v_row, v_col in ants.vision_offsets_2:
			visible.append((a_row + v_row, a_col + v_col))
	return visible

def fvisible(ants, loc):
	' determine which squares are visible to the given player '
	cdef int mx
	cdef int a_row, a_col, row, col
	visible = []
	if ants.vision == None:
		if not hasattr(ants, 'vision_offsets_2'):
			# precalculate squares around an ant to set as visible
			ants.vision_offsets_2 = []
			mx = int(sqrt(ants.viewradius2))
			for d_row in range(-mx,mx+1):
				for d_col in range(-mx,mx+1):
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
			for v_row, v_col in ants.vision_offsets_2:
				ants.vision[a_row + v_row][a_col + v_col] = True
	row, col = loc
	return ants.vision[row][col]

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
			directions = fdirection(ants, loc, dest)
			is_passable = False
			for direction in directions:
				next_loc = fdestination(ants, loc, direction)
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
		self.logs = csv.writer(open('log_frozenants.csv', 'wb'))
		self.hills = []
		self.waypoints = []
		self.unseen = []
		self.visible = []
		self.visible_frontier = []
		self.MDPs = []
		self.stored_MDPs = {}
		for row in range(0, ants.rows):
			for col in range(0, ants.cols):
				self.unseen.append((row, col))
		for row in range(0, ants.rows, 3):
			for col in range(0, ants.cols, 3):
				self.waypoints.append((row, col))

	# do turn is run once per turn
	# the ants class has the game state and is updated by the Ants.run method
	# it also has several helper methods to use

	def do_turn(self, ants):
		# loop through all my ants and try to give them orders
		# the ant_loc is an ant location tuple in (row, col) form
		cdef int dist, min_dist
		orders = {}
		def do_move_direction(loc, direction):
			new_loc = fdestination(ants, loc, direction)
			if (ants.unoccupied(new_loc) and new_loc not in orders.keys()):
				ants.issue_order((loc, direction))
				orders[new_loc] = loc
				return True
			else:
				return False

		targets = {}
		def do_move_location(loc, dest):
			if loc in orders.values():
				return False
			directions = fdirection(ants, loc, dest)
			for direction in directions:
				if do_move_direction(loc, direction):
					targets[dest] = loc
					available_ants.remove(loc)
					return True
			return False

		def get_adjacent(loc):
			directions = ('n', 'e', 's', 'w')
			adjacent = []
			for direction in directions:
				adjacent.append(ants.destination(loc, direction))
			return adjacent

		def MDP(loc, type):
			cdef int Q, cost, cost_increment
			cdef int row, col
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

		self.MDPs = [[0] * ants.cols for row in range(ants.rows)]
		available_ants = ants.my_ants()

		self.logs.writerow([(20, 20), fvisible(ants, (20, 20)), ants.visible((20, 20)), ants.passable((20, 20)), ants.unoccupied((20, 20))])

		# Prevent stepping on own hill
		for hill_loc in ants.my_hills():
			if hill_loc in ants.my_ants():
				orders[hill_loc] = None

		# find close food
		dists = []
		for ant_loc in available_ants: 
			for food_loc in ants.food():
				dist = fdistance(ants, ant_loc, food_loc)
				dists.append((dist, ant_loc, food_loc))
		dists.sort()
		for dist, ant_loc, food_loc in dists:
			if straight_path(ants, ant_loc, food_loc):
				do_move_location(ant_loc, food_loc)

		# explore unseen areas
		if len(self.unseen) > 0:
			self.visible = get_all_visible(ants)
			for vis_loc in self.visible:
				if vis_loc in self.unseen:
					self.unseen.remove(vis_loc)
					if vis_loc in self.visible_frontier:
						self.visible_frontier.remove(vis_loc)
					for adj in get_adjacent(vis_loc):
						if adj in self.unseen and adj not in self.visible_frontier:
							self.visible_frontier.append(adj)
			dists = []
			for ant_loc in available_ants: 
				for frontier_loc in self.visible_frontier:
					dist = fdistance(ants, ant_loc, frontier_loc)
					dists.append((dist, ant_loc, frontier_loc))
			dists.sort()
			for dist, ant_loc, frontier_loc in dists:
				if ants.time_remaining() < 50:
					break
				if straight_path(ants, ant_loc, frontier_loc):
					do_move_location(ant_loc, frontier_loc)

		for ant_loc in available_ants:
			if do_move_direction(ant_loc, ('n', 'e', 's', 'w')[randint(0, 3)]):
				break

		# Unblock own hill
		for hill_loc in ants.my_hills():
			if hill_loc in ants.my_ants():
				for direction in ('s', 'e', 'w', 'n'):
					if do_move_direction(hill_loc, direction):
						break
