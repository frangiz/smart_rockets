import math
import pygame
import random
import json
from itertools import count
from collections import namedtuple

Point = namedtuple('Point', 'x y')


# Global config
WIN_SIZE = [600, 800]


# ------------------------------------------------------------------------------
class Rocket:
    _id = count(0)

    def __init__(self):
        self.genome = [random.randint(-7, 7) for _ in range(300)]
        self.fitness = -1
        self.id = next(self._id)
        self.alive = True

        self.angle = 0
        self.pos = Point(0, 0)

    def __repr__(self):
        items = ("%s: %r" % (k, v) for k, v in self.__dict__.items())
        return "<%s: {%s}>" % (self.__class__.__name__, ', '.join(sorted(items)))

    def draw(self, surface):
        border = [(0, 0), (-10, 10), (10, 0), (-10, -10)]
        translated = self._translate(border, self.pos)
        rotated = [self._rotate_point(self.pos, p, self.angle) for p in translated]
        border_color = (255, 255, 9) if self.alive else (255, 0, 0)
        pygame.draw.polygon(surface, border_color, rotated, 0)

    def apply_force(self, force):
        radians = math.radians(self.angle)
        x = self.pos.x + math.cos(radians) * force
        y = self.pos.y + math.sin(radians) * force
        self.pos = Point(x, y)

    def _translate(self, border, position):
        result = []
        for p in border:
            result.append([sum(x) for x in zip(p, position)])
        return result

    def _rotate_point(self, origin, point, angle):
        ox, oy = origin
        px, py = point
        radians = math.radians(angle)

        qx = ox + math.cos(radians) * (px - ox) - math.sin(radians) * (py - oy)
        qy = oy + math.sin(radians) * (px - ox) + math.cos(radians) * (py - oy)

        return qx, qy


# ------------------------------------------------------------------------------
class Simulation:
    def __init__(self, win_size):
        self.win_size = pygame.Rect((0, 0), win_size)
        self.info_font = pygame.font.SysFont("comicsansms", 25)
        self.restart()

    def restart(self):
        self.rockets = []
        self.index = 0

        self.obstacles = []
        self.generation = 1
        self.best_fitness = 0
        self.fps = 30

        # from config file
        cnf = self._load_config()
        self.population = int(cnf['population'])
        for obst in cnf['obstacles']:
            self.obstacles.append(pygame.Rect(obst))
        self.start = Point(int(cnf['start_pos'][0]), int(cnf['start_pos'][1]))
        self.goal = Point(int(cnf['goal'][0]), int(cnf['goal'][1]))

        self.rockets = [Rocket() for _ in range(self.population)]
        self.rockets = self._reset_rockets(self.rockets)

    def update(self):
        for rocket in self.rockets:
            if rocket.alive:
                rocket.apply_force(3)
                rocket.angle += rocket.genome[self.index % len(rocket.genome)]
        self.index += 1
        self._check_collision()
        self.rockets = self._fitness(self.rockets)

    def draw(self, surface):
        surface.fill((0, 0, 0))
        self._draw_start_platform(surface)
        self._draw_goal(surface)
        for rocket in self.rockets:
            rocket.draw(surface)
        self._draw_overlay(surface)
        self._draw_obstacles(surface)

        pygame.display.flip()

    def next_gen(self):
        rockets = self._selection(self.rockets)
        rockets = self._crossover(rockets)
        rockets = self._mutation(rockets)
        rockets = self._reset_rockets(rockets)
        self.rockets.clear()
        self.rockets = rockets
        self.index = 0
        self.generation += 1

    def alive_rockets(self):
        return sum(1 for r in self.rockets if r.alive)

    def found_solution(self):
        return any([r for r in self.rockets if self._distance(r.pos, self.goal) < 10])

    def _reset_rockets(self, rockets):
        for rocket in rockets:
            rocket.pos = Point(self.start.x, self.start.y + 3 - 50)
            rocket.angle = 270
            rocket.alive = True
        return rockets

    def _check_collision(self):
        for rocket in self.rockets:
            # Check if the rocket flies over any edge.
            if rocket.pos.x < 0 or rocket.pos.x > self.win_size.width:
                rocket.alive = False
            elif rocket.pos.y < 0 or rocket.pos.y > self.win_size.height:
                rocket.alive = False
            # Check if the rocket flies into a obstacle.
            for obs in self.obstacles:
                    if obs.collidepoint(rocket.pos):
                        rocket.alive = False

    def _draw_overlay(self, surface):
        best_fitness = round(max(self.rockets, key=lambda x: x.fitness).fitness)
        self.best_fitness = max(self.best_fitness, best_fitness)

        labels = [
            "Generation: " + str(self.generation),
            "FPS: " + str(self.fps),
            "Best fitness: " + str(best_fitness) + '/' + str(self.best_fitness),
            "Alive: " + str(self.alive_rockets())]
        y_pos = 10
        for label in labels:
            surface.blit(self.info_font.render(
                label, 2, (255, 255, 255)), (10, y_pos))
            y_pos += 30

    def _draw_start_platform(self, surface):
        x0 = self.start.x - 20
        x1 = x0 + 40
        y = self.start.y
        pygame.draw.line(surface, (0, 0, 255), [x0, y], [x1, y], 6)

    def _draw_goal(self, surface):
        pygame.draw.circle(surface, (0, 255, 0), self.goal, 10)

    def _draw_obstacles(self, surface):
        for obs in self.obstacles:
            pygame.draw.rect(surface, (255, 102, 0), obs)

    def _fitness(self, rockets):
        total_distance = self._distance(self.start, self.goal)
        for rocket in rockets:
            d = self._distance(rocket.pos, self.goal)
            rocket.fitness = 100 - (d / total_distance) * 100
        return rockets

    def _selection(self, rockets):
        rockets = sorted(rockets, key=lambda r: r.fitness, reverse=True)
        result = rockets[:int(0.2 * len(rockets))]
        if random.uniform(0.0, 1.0) <= 0.1:
            print('Selection(): Adding the two least fittest rockets.')
            rockets.extend(rockets[-2:])
        return result

    def _crossover(self, rockets):
        offspring = []
        for _ in range(int((self.population - len(rockets)) / 2)):
            parent1 = random.choice(rockets)
            parent2 = random.choice([r for r in rockets if r != parent1])
            child1 = Rocket()
            child2 = Rocket()
            split = random.randint(0, len(parent1.genome))
            child1.genome = parent1.genome[0:split] + parent2.genome[split:]
            child2.genome = parent2.genome[0:split] + parent1.genome[split:]

            offspring.append(child1)
            offspring.append(child2)

        rockets.extend(offspring)
        return rockets

    def _mutation(self, rockets):
        for rocket in rockets:
            for i, _ in enumerate(rocket.genome):
                if random.uniform(0.0, 1.0) <= 0.1:
                    rocket.genome[i] = random.randint(-7, 7)
        return rockets

    def _load_config(self):
        cnf = {}
        with open('config.json', 'r') as json_file:
            cnf = json.load(json_file)
        return cnf

    def _distance(self, p1, p2):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)


# ------------------------------------------------------------------------------
def main():
    pygame.init()
    sim = Simulation(WIN_SIZE)
    surface = pygame.display.set_mode(WIN_SIZE)
    pygame.display.set_caption('smart rockets')
    done = False
    clock = pygame.time.Clock()

    while not done:
        clock.tick(sim.fps)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_q:
                    done = True
                elif event.key == pygame.K_a and sim.fps < 300:
                    sim.fps += 5
                elif event.key == pygame.K_z and sim.fps > 5:
                    sim.fps -= 5
                elif event.key == pygame.K_r:
                    sim.restart()
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:  # Right mouse button
                    x, y = pygame.mouse.get_pos()
                    sim.goal = Point(x, y)
        if sim.alive_rockets() == 0:
            sim.next_gen()
        if not sim.found_solution():
            sim.update()
            sim.draw(surface)


if __name__ == '__main__':
    main()
