import random, json, math, time
from itertools import accumulate
from enum import Enum

try:
	from termcolor import cprint, colored
except ModuleNotFoundError:
	def cprint(text, color=None, on_color=None, attrs=None, **kwargs):
		print(text, **kwargs)			
	def colored(text, color=None, on_color=None, attrs=None):
		return text
	install = None
	while not install or install[0].lower() not in "yn":
		install = input("You appear to be missing the termcolor module, would you like to install it? (Y/N)")
	if install[0].lower() == "n":
		print("Continuing without colored text")
	else:
		import subprocess
		returncode = subprocess.call(["pip", "install", "termcolor"])
		if returncode:
			print("Failed to install termcolor module; continuing without colored text")
		else:
			from termcolor import cprint, colored
			
#A text-based RPG game based on Minecraft

def one_in(x):
	"Returns True with a probability of 1/x, otherwise returns False"
	return x <= 1 or random.randint(1, x) == 1

def x_in_y(x, y):
	"Returns True with a probability of x/y, otherwise returns False"
	return random.uniform(0, y) < x

def choice_input(*choices, return_text=False):
	for index, choice in enumerate(choices):
		print(f"{index + 1}. {choice}")
	while True:
		try:
			choice = int(input(">> "))
		except ValueError:
			continue
		else:
			if 1 <= choice <= len(choices):
				return choices[choice - 1] if return_text else choice

def yes_no(message):
	m = input(message + " (Y/N) ")
	return len(m) > 0 and m[0].lower() == "y"
	
class MobBehaviorType(Enum):
	passive = 0 #Passive; won't attack even if attacked
	neutral = 1 #Neutral; will become hostile if attacked
	hostile = 2 #Hostile; may attack on sight

class WeightedList:
	
	def __init__(self):
		self.choices = []
		self.weights = []
		self.cumulative_weights = None
		
	def add(self, value, weight):
		if weight > 0:
			self.choices.append(value)
			self.weights.append(weight)
			self.cumulative_weights = None 
	
	def clear(self):
		self.choices.clear()
		self.weights.clear()
		self.cumulative_weights = None 
		
	def pick(self):
		if len(self.choices) == 0:
			raise IndexError("cannot pick from an empty weighted list")
		if not self.cumulative_weights:
			self.cumulative_weights = list(accumulate(self.weights))
		return random.choices(self.choices, cum_weights=self.cumulative_weights)[0]

mobs_dict = json.load(open("mobs.json"))

class MobType:
	
	def __init__(self, name, weight, max_hp, behavior: MobBehaviorType, death_drops, night_mob, attack_strength):
		self.name = name
		self.weight = weight
		self.hp = max_hp
		self.behavior = behavior
		self.death_drops = death_drops
		self.night_mob = night_mob
		self.attack_strength = attack_strength
		
	@staticmethod
	def from_dict(d):
		name = d["name"]
		HP = d["HP"]
		b = d["behavior"]
		weight = d["weight"]
		if b == "passive":
			behavior = MobBehaviorType.passive
		elif b == "neutral":
			behavior = MobBehaviorType.neutral
		elif b == "hostile":
			behavior = MobBehaviorType.hostile
		else:
			raise ValueError(f"Invalid behavior type {b!r}")
		attack_strength = d.get("attack_strength")
		if attack_strength is None and b != "passive":
			raise ValueError("Non-passive mobs require an attack strength")
		death_drops = d.get("death_drops", {})
		for drop in death_drops:
			data = death_drops[drop]
			if not isinstance(data, dict):
				raise TypeError("Each entry in death_drops must be a dict")
			if "chance" in data and (not isinstance(data["chance"], list) or len(data["chance"]) != 2):
				raise TypeError("chance must be a 2-item list")
			if "quantity" in data and not (isinstance(data["quantity"], int) or (isinstance(data["quantity"], list) and len(data["quantity"]) == 2)):
				raise TypeError("quantity muat be an int or a 2-item list")
		night_mob = d.get("night_mob", False)
		return MobType(name, weight, HP, behavior, death_drops, night_mob, attack_strength)

mob_types = {}

for mob_dict in mobs_dict:
	name = mob_dict["name"]
	mob_types[name] = MobType.from_dict(mob_dict)	

#passive_mob_types = list(filter(lambda typ: mob_types[typ].behavior == MobBehaviorType.passive, mob_types))
#night_mob_types = list(filter(lambda typ: mob_types[typ].night_mob, mob_types))
day_mob_types = WeightedList()
night_mob_types = WeightedList()
for typ in mob_types:
	mob_type = mob_types[typ]
	if mob_type.night_mob:
		night_mob_types.add(typ, mob_type.weight)
	else:
		day_mob_types.add(typ, mob_type.weight)

class Mob:
	
	def __init__(self, name, HP, behavior: MobBehaviorType, death_drops, attack_strength):
		self.name = name
		self.HP = HP
		self.behavior = behavior
		self.death_drops = death_drops
		self.attack_strength = attack_strength
		
	@staticmethod
	def new_mob(typ: str):
		typ = mob_types[typ]
		return Mob(typ.name, typ.hp, typ.behavior, typ.death_drops, typ.attack_strength)
	
	def damage(self, amount, player):
		self.HP -= amount
		if self.HP <= 0:
			print(f"The {self.name.lower()} is dead!")
			self.on_death(player)
			
	def on_death(self, player):
		if self.death_drops:
			got = {}
			for drop in self.death_drops:
				r = self.death_drops[drop]
				q = r.get("quantity", 1)
				x, y = r.get("chance", [1, 1])
				if isinstance(q, list):
					amount = random.randint(*q)
				elif isinstance(q, int):
					amount = q
				else:
					raise TypeError("Amount must be an int or a 2-item list")
				if amount > 0 and x_in_y(x, y):
					if drop == "EXP":
						player.EXP += amount
					else:
						got[drop] = amount
			if got:
				print("You got: ")
				for item in got:
					print(f"{got[item]}x {item}")
					player.add_item(item, got[item])

class ToolData:
	
	def __init__(self, damage, durability, attack_speed, mining_mult):
		self.damage = damage
		self.durability = durability
		self.attack_speed = attack_speed
		self.mining_mult = mining_mult
	
	@staticmethod	
	def from_dict(d):
		damage = d.get("damage", 1)
		durability = d["durability"]
		attack_speed = d.get("attack_speed", 4)
		mining_mult = d.get("mining_mult", 1)
		return ToolData(damage, durability, attack_speed, mining_mult)	

class Recipe:
	
	def __init__(self, quantity, components, tool_data=None):
		self.quantity = quantity
		self.components = components
		self.tool_data = tool_data
		
	@staticmethod
	def from_dict(d):
		quantity = d.get("quantity", 1)
		components = d["components"]
		tool_data = d.get("tool_data")
		if tool_data:
			tool_data = ToolData.from_dict(tool_data)
		return Recipe(quantity, components, tool_data)
		
r = json.load(open("recipes.json"))
recipes = {}
for name in r:
	recipe = r[name]
	recipes[name] = Recipe.from_dict(recipe)

foods = json.load(open("foods.json"))
			
class Time:
	
	def __init__(self):
		self.mins = 0
		self.secs = 0
		
	def is_night(self):
		return self.mins >= 20
	
	def advance(self, secs):
		was_night = self.is_night()
		last_mins = self.mins
		self.secs += secs
		while self.secs >= 60:
			self.mins += 1
			self.secs -= 60
		self.mins %= 40
		is_night = self.is_night()
		if was_night ^ is_night:
			if is_night:
				cprint("It is now nighttime", "blue")
			else:
				cprint("It is now daytime", "blue")
		elif last_mins < 18 and self.mins >= 18:
			cprint("The sun begins to set", "blue")
		elif last_mins < 38 and self.mins >= 38:
			cprint("The sun begins to come up", "blue")

class Player:
	
	def __init__(self):
		self.HP = 20
		self.hunger = 20
		self.food_exhaustion = 0
		self.saturation = 5
		self.inventory = {}
		self.tools = []
		self.curr_weapon = None
		self.EXP = 0
		self.time = Time()
		
	def advance_time(self, secs):
		self.time.advance(secs)
		
	def damage(self, amount, death_reason=None, physical=True):
		if amount <= 0:
			return
		cprint(f"You take {amount} damage!", "red")
		self.HP -= amount
		if physical:
			self.mod_food_exhaustion(0.1)
		if self.HP <= 0:
			self.die(death_reason)
		print(f"HP: {self.HP}/20")
		
	def die(self, death_reason=None):
		print("You died!")
		if death_reason:
			print(death_reason)
		print(f"\nScore: {self.EXP}")
		exit()
		
	def print_health(self):
		print(f"HP: {self.HP}/20")
		
	def heal(self, amount):
		if amount <= 0:
			return False
		old_hp = self.HP
		self.HP = min(self.HP + amount, 20)
		healed_by = self.HP - old_hp
		if healed_by > 0:
			cprint(f"You are healed by {healed_by} HP.", "green")
			self.print_health()
			return True
		return False
	 
	def tick(self):
		if self.HP < 20:
			if (self.hunger == 20 or (self.hunger >= 18 and one_in(8))) and self.heal(1):
				self.mod_food_exhaustion(6)
		self.advance_time(0.5)
	
	def mod_food_exhaustion(self, amount):
		self.food_exhaustion += amount
		if self.food_exhaustion >= 4:
			if self.saturation == 0:
				self.hunger -= 1
			else:
				self.saturation -= 1
			self.print_hunger()
			self.food_exhaustion = 0		
	
	def print_hunger(self):
		if self.saturation == 0:
			cprint(f"Hunger: {self.hunger}/20", "yellow")
		else:
			print(f"Hunger: {self.hunger}/20")
	
	def add_item(self, item, amount=1):
		if item in self.inventory:
			self.inventory[item] += amount
		else:
			self.inventory[item] = amount
			
	def add_tool(self, tool):
		self.tools.append(tool)
			
	def remove_item(self, item, amount):
		if amount <= 0:
			return
		if item not in self.inventory or amount > self.inventory[item]:
			raise ValueError("Tried to remove more of item than available in inventory")
		self.inventory[item] -= amount
		if self.inventory[item] <= 0:
			del self.inventory[item]
			
	def armed(self):
		return self.curr_weapon is not None
		
	def attack_damage(self):
		return self.curr_weapon.damage if self.armed() else 1
		
	def attack_speed(self):
		return self.curr_weapon.attack_speed if self.armed() else 4
		
	def has_item(self, item, amount=1):
		if item not in self.inventory:
			return False
		return self.inventory[item] >= amount
		
	def has_any_item(self, names):
		return any(name in self.inventory for name in names)
		
	def has_tool(self, tool_name):
		return any(tool.name == tool_name for tool in self.tools)
	
	def has_any_tool(self, tool_names):
		l1 = set(tool_names)
		l2 = set(tool.name for tool in self.tools)
		return not l1.isdisjoint(l2)
		
	def restore_hunger(self, hunger, saturation):
		if self.hunger < 20:
			self.hunger = min(self.hunger + hunger, 20)
			self.saturation = min(self.saturation + saturation, self.hunger)
			self.print_hunger()
			
	def can_make_recipe(self, recipe):
		for component in recipe.components:
			name, amount = component
			if not self.has_item(name, amount):
				return False
		return True	
			
	def decrement_tool_durability(self):
		tool = self.curr_weapon
		if tool:
			tool.durability -= 1
			if tool.durability < 0:
				cprint(f"Your {tool.name} is destroyed!", "red")
				self.tools.remove(tool)
				self.curr_weapon = None
			else:
				print(f"Durability: {durability_message(tool.durability, tool.max_durability)}")
			
	def switch_weapon_menu(self):
		if len(self.tools) > 0:
			options = [] 
			for tool in self.tools:
				options.append(f"{tool.name} - Durability {durability_message(tool.durability, tool.max_durability)}")
			options.append("Unarmed")
			print("Which weapon would you like to switch to?")
			choice = choice_input(*options)
			if choice == len(self.tools) + 1:
				print("You decide to go unarmed")
				self.curr_weapon = None
			else:
				weapon = self.tools[choice - 1]
				print(f"You switch to your {weapon.name}")
				self.curr_weapon = weapon
			
class Tool:
	
	def __init__(self, name, damage, durability, mining_mult, attack_speed):
		self.name = name
		self.damage = damage
		self.durability = durability
		self.max_durability = durability
		self.mining_mult = mining_mult
		self.attack_speed = attack_speed
				
def durability_message(durability, max_durability):
	durability_msg = f"{durability}/{max_durability}"
	if durability <= max_durability // 4:
		color = "red"
	elif durability <= max_durability // 2:
		color = "yellow"
	else:
		color = "green"
	return colored(durability_msg, color)
	
def random_battle(player, night_mob, action_verb="exploring"):
	if night_mob:
		choices = night_mob_types
	else:
		choices = day_mob_types
	mob = Mob.new_mob(choices.pick())
	#mob = Mob.new_mob("Creeper")
	mob_name = mob.name.lower()
	print(f"You found a {mob_name} while {action_verb}{'!' if mob.behavior == MobBehaviorType.hostile else '.'}")
	if mob.behavior == MobBehaviorType.hostile and not mob_name.endswith("creeper") and one_in(2):
		cprint(f"The {mob_name} attacks you!", "red")
		player.damage(mob.attack_strength)
	creeper_turn = 0
	choice = choice_input("Attack", "Flee" if mob.behavior == MobBehaviorType.hostile else "Ignore")
	if choice == 1:
		if mob.behavior != MobBehaviorType.passive and len(player.tools) > 0 and yes_no("Would you like to switch weapons?"):
			player.switch_weapon_menu()
		run = 0
		while True:
			if run > 0:
				run -= 1
				if run == 0:
					print(f"The {mob_name} stops running.")
			player.mod_food_exhaustion(0.1)
			if run > 0 and x_in_y(3, 10):
				print(f"You miss the {mob_name} attacking it while it was fleeing.")
			else:			
				damage = player.attack_damage()
				is_critical = one_in(10)
				base_damage = damage
				if is_critical:
					damage = int(damage * 1.5)
					is_critical = is_critical and damage > base_damage
				print(f"You attack the {mob_name}.{' Critical!' if is_critical else ''}") #TODO: Vary this message based on wielded weapon
				player.decrement_tool_durability()
				mob.damage(damage, player)
				if mob.HP <= 0:
					break
				if mob.behavior == MobBehaviorType.passive:
					if not one_in(3) and run == 0:
						print(f"The {mob_name} starts running away.")
						run += random.randint(3, 5)
			attack_speed = player.attack_speed() #Attack speed controls the chance of being attacked by a mob when we attack
			if mob_name.endswith("creeper"):
				creeper_turn += 1
				if creeper_turn > 2 and not one_in(creeper_turn - 1): #Increasing chance to explode after the first 2 turns
					damage = max(random.randint(1, mob.attack_strength) for _ in range(3)) #attack_strength defines explosion power for creepers
					print("The creeper explodes!")
					player.damage(damage, "Killed by a creeper's explosion")
					explosion_power = mob.attack_strength // 7
					if action_verb == "mining":
						minables.add("Stone", 3000) #Explosions drop the block instead of the item
						minables.add("Coal Ore", 124)
						minables.add("Iron Ore", 72)
						minables.add("Lapis Lazuli Ore", 3)
						minables.add("Gold Ore", 7)
						minables.add("Diamond Ore", 3)
						num = int((explosion_power * random.uniform(0.75, 1.25)) ** 2) + 1
						found = {}
						for _ in range(num):
							if not one_in(3):
								s = minables.pick()
								if s in found:
									found[s] += 1
								else:
									found[s] = 1
						if len(found) > 0:
							print("You got the following items from the explosion:")
							for item in found:
								print(f"{found[item]}x {item}")
								player.add_item(item, found[item])
					else:
						grass = random.randint(explosion_power // 3, explosion_power) + 1
						dirt = int((explosion_power * random.uniform(0.75, 1.25)) ** 2) + 1
						player.add_item("Dirt", dirt)
						player.add_item("Grass", grass)
						print(f"You got {grass}x Grass and {dirt}x Dirt from the explosion")
					break
				else:
					print("The creeper flashes...")
			elif mob.behavior != MobBehaviorType.passive and x_in_y(1, attack_speed) and not one_in(4): #I use x_in_y instead of one_in because x_in_y works with floats
				print(f"The {mob_name} attacks you!")
				player.damage(mob.attack_strength)
			player.tick()
			choice = choice_input("Attack", "Ignore" if mob.behavior == MobBehaviorType.passive else "Flee")
			if choice == 2:
				return

splashes = open("splashes.txt").read().splitlines()

print("MINCERAFT" if one_in(10000) else "MINECRAFT") #An extremely rare easter egg
cprint(random.choice(splashes), "yellow", attrs=["bold"])
print()
choice = choice_input("Play", "Quit")
if choice == 2:
	exit()
	
player = Player()

while True:
	player.tick()
	if player.time.is_night():
		print("It is currently nighttime")
	player.print_health()
	player.print_hunger()
	if player.curr_weapon:
		weapon = player.curr_weapon
		print(f"Current weapon: {player.curr_weapon.name} - Durability {durability_message(weapon.durability, weapon.max_durability)}")
	choice = choice_input("Explore", "Inventory", "Craft", "Switch Weapon", "Eat", "Mine", "Smelt")
	if choice == 1:
		print("You explore for a while.")
		player.mod_food_exhaustion(0.001)
		player.advance_time(random.randint(10, 30))
		mob_chance = 3 if player.time.is_night() else 8
		if one_in(mob_chance):
			random_battle(player, player.time.is_night())
		elif x_in_y(3, 5):
			explore_finds = [("Grass", 8), ("Dirt", 1), ("Wood", 4)]
			choices = [val[0] for val in explore_finds]
			weights = [val[1] for val in explore_finds]
			found = random.choices(choices, weights=weights)[0]
			print(f"You found 1x {found}")
			player.add_item(found)
	elif choice == 2:
		if len(player.inventory) == 0:
			print("There is nothing in your inventory")
		else:
			print("Your inventory:")
			for item in player.inventory:
				print(f"{player.inventory[item]}x {item}")
			print("Your tools:")
			for index, tool in enumerate(player.tools):
				print(f"{index+1}. {tool.name} - Durability {tool.durability}/{tool.max_durability}")
	elif choice == 3:
		craftable = []
		for recipe in recipes:
			info = recipes[recipe]
			if player.can_make_recipe(info):
				craftable.append((recipe, recipes[recipe]))
		if len(craftable) == 0:
			print("There are no items that you have the components to craft")
		else:
			print("Items you can craft:")
			for item in craftable:
				name, info = item
				quantity = info.quantity
				string = f"{quantity}x {name} | Components: "
				components = info.components
				string += ", ".join(f"{c[1]}x {c[0]}" for c in components)
				print(string)
				print()
			print("What would you like to craft?")
			item_name = input()
			item = next((v for v in craftable if v[0] == item_name), None)
			if item is not None:
				name, info = item
				components = info.components
				quantity = info.quantity
				for component in components:
					player.remove_item(*component)
				if info.tool_data is not None:
					tool_data = info.tool_data
					damage = tool_data.damage
					durability = tool_data.durability
					mining_mult = tool_data.mining_mult
					attack_speed = tool_data.attack_speed
					player.add_tool(Tool(name, damage, durability, mining_mult, attack_speed))
				else:
					player.add_item(name, quantity)
				print(f"You have crafted {quantity}x {name}")
			else:
				print("Invalid item")
	elif choice == 4:
		if len(player.tools) > 0:
			player.switch_weapon_menu()
		else:
			print("You don't have any weapons")
	elif choice == 5:
		foods_in_inv = list(filter(lambda item: item in foods, player.inventory))
		if foods_in_inv:
			choices = foods_in_inv + ["Cancel"]
			print("Which food would you like to eat?")
			num = choice_input(*choices)
			if num <= len(foods_in_inv):
				 food = foods_in_inv[num - 1]
				 player.remove_item(food, 1)
				 print(f"You eat the {food}.")
				 saturation = foods[food]["saturation"]
				 hunger = foods[food]["hunger"]
				 player.restore_hunger(hunger, saturation)
		else:
			print("You don't have anything to eat")
	elif choice == 6:
		if any("Pickaxe" in tool.name for tool in player.tools):
			if player.curr_weapon and "Pickaxe" in player.curr_weapon.name:
				tiers = ["Wooden Pickaxe", "Stone Pickaxe", "Iron Pickaxe"]
				tier_num = tiers.index(player.curr_weapon.name) + 1
				minables = WeightedList()
				minables.add("Stone", 2000)
				minables.add("Coal", 124)
				if tier_num > 1:
					minables.add("Raw Iron", 72)
					minables.add("Lapis Lazuli", 3)
					if tier_num > 2:
						minables.add("Raw Gold", 7)
						minables.add("Diamond", 3)
				found = minables.pick()
				if found == "Lapis Lazuli":
					quantity = random.randint(4, 9)
				else:
					quantity = 1
				print(f"You found {quantity}x {found}")
				player.add_item(found, quantity)
				player.mod_food_exhaustion(0.005)
				if found == "Stone":
					base_mine_time = 1.5
				else:
					base_mine_time = 3
				mine_mult = player.curr_weapon.mining_mult
				mine_time = round(base_mine_time / mining_mult, 2)
				player.advance_time(random.randint(1, 3))
				player.decrement_tool_durability()
				mob_chance = 10 if player.time.is_night() else 15
				mob_chance *= math.sqrt(mine_mult)
				mob_chance = round(mob_chance)
				if one_in(mob_chance):
					random_battle(player, True, "mining")
			else:
				print("You need to switch to your pickaxe to mine")
		else:
			print("You can't mine without a pickaxe")
	elif choice == 7:
		if player.has_item("Furnace"):
			smeltable = {
				"Raw Iron": "Iron Ingot",
				"Iron Ore": "Iron Ingot",
				"Coal Ore": "Coal"
			}
			fuel_sources = {
				"Coal": 80,
				"Wooden Pickaxe": 10,
				"Wooden Sword": 10
			}
			item_sources = list(filter(lambda item: item in player.inventory, fuel_sources))
			tool_sources = list(filter(lambda tool: any(t.name == tool for t in player.tools), fuel_sources))
			if player.has_any_item(item_sources) or player.has_any_tool(tool_sources):
				can_smelt = list(filter(lambda item: item in smeltable, player.inventory))
				if can_smelt:
					print("Smelt which item?")
					strings = list(map(lambda s: f"{s} -> {smeltable[s]}", can_smelt))
					choice = choice_input(*strings)
					smelted = can_smelt[choice - 1]
					smelt_into = smeltable[smelted]
					print("Which fuel source to use?")
					all_sources = item_sources + tool_sources
					choice = choice_input(*all_sources)
					source = all_sources[choice - 1]
					dur = fuel_sources[source]
					is_tool = source in tool_sources
					print("Smelting...")
					time.sleep(dur / 10)
					player.advance_time(dur)
					if is_tool:
						tool = next((t for t in player.tools if t.name == source), None)
						if tool is not None:
							player.tools.remove(tool)
						else:
							cprint("Could not find the tool to remove", "yellow")
					else:
						player.remove_item(source, 1)
					player.remove_item(smelted, 1)
					player.add_item(smelt_into)
					print(f"You got 1x {smelt_into}")
				else:
					print("You don't have anything to smelt")
			else:
				print("You need a fuel source to smelt items")
		else:
			print("You need a furnace to smelt items")	