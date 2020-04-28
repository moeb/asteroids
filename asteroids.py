#!/usr/bin/env python3.6

import math
import time
import random

import pymunk
import pyglet
from pyglet import gl
from pyglet.window import key
from pyglet.graphics import Batch
from pyglet.sprite import Sprite

def main():
    # the entry point of the game
    # look at this if you want to understand
    # the game

    width = 1024
    height = 768
    win_size = (width, height)
    # bounds in wich objects may exist
    bounds = math.hypot(*win_size)/2 + 300
    # create a window; opengl context inclusive
    window = pyglet.window.Window(*win_size);

    # create the world space
    # (this part belongs/is to the model)
    world = World(win_size, bounds)
    # for the end we need a label and time played
    score_view = ScoreView(win_size)

    @world.collision_handler(Asteroid, Bullet)
    def begin(arbiter, space, data):
        for shape in arbiter.shapes:
            try:
                model, controller = world.get_by_shape(shape)
                controller.delete(model)
            except KeyError:
                # collision handler gets called multiple times
                # even after deletion it seems
                # this is an error in pymunk/chipmunk
                print(shape in space.shapes)
                #pass
        return False


    @world.collision_handler(Spaceship, Asteroid)
    def post_solve(arbiter, space, data):
        try:
            for shape in arbiter.shapes:
                model, controller = world.get_by_shape(shape)
                # create label with score
                score_view.show_score()
                # stop time
                world.done = True
        except KeyError:
            pass

    # the player controls a spaceship
    player = Player(world)
    # the player is an event-handler for the Window class of pyglet
    # where it gets it's keyboard events
    window.push_handlers(player)
    # the world needs the player for reference
    world.register_player(player)

    # the other controller is the AsteroidSpammer
    # whose task is to spam Asteroids
    # needs the player for reference
    asteroid_spammer = AsteroidSpammer(world, win_size, player)

    # the window controls when it is drawn
    @window.event
    def on_draw():
        window.clear()
        # move world space, so the spaceship is in the middle
        world.translate()
        # every view is registered with View
        # so View.draw draws everything
        View.draw()
        # if there is a score:
        score_view.draw()

    # everything that needs to be done continually
    # has to be in this function
    def interval_cb(dt):
        # world time has to go on
        world.step(dt)
        # controll of the ship is in world time
        player.step(dt)
        # the AsteroidSpammer may want to spam an Asteroid
        asteroid_spammer.step(dt)

    # now schedule the callback ~30 times per second
    pyglet.clock.schedule_interval(interval_cb, 1/30)

    # finally we are done :)
    # lets run the app
    pyglet.app.run()



class World:
    """
    world model
    ever object must be registered with world
    
    world is responsible for removing out of bounds objects
    and progressing pymunk time

    dispatches events for collision handling
    """
    def __init__(self, window_size, bounds):
        self._time = 0.0
        self._space = pymunk.Space()
        self._space.gravity = (0, 0)
        self._models = []
        self._shapes = {}
        self._bounds = bounds
        self._player = None
        self._mid = (window_size[0]/2, window_size[1]/2)
        self._collision_handlers = {}
        # when the game is done
        # switch this boolean
        self.done = False

    def register_player(self, player):
        self._player = player

    def _register_model_type(self, model_type):
        if model_type not in self._collision_handlers:
            self._collision_handlers[model_type] = len(self._collision_handlers)+1
            model_type.collision_type = len(self._collision_handlers)

    def collision_handler(self, m1, m2):
        """
        decorator for registering a collision handler
        @world.collision_handler(Asteroid, Bullet)
        def pre_solve(arbiter, space, data):
            do_stuff()
        """
        self._register_model_type(m1)
        self._register_model_type(m2)
        # handler types from pymunk
        allowed_handler_types = [
            'pre_solve',
            'post_solve',
            'begin',
            'separate'
        ]
        def _(fun):
            assert fun.__name__ in allowed_handler_types
            handler = self._space.add_collision_handler(
                self._collision_handlers[m1],
                self._collision_handlers[m2])
            setattr(handler, fun.__name__, fun)
        return _

    def add(self, model, controller):
        self._space.add(model.body, model.shape)
        self._models.append((model, controller))
        self._shapes[model.shape] = (model, controller)

    def remove(self, model, controller):
        self._space.remove(model.body, model.shape)
        self._models.remove((model, controller))
        del self._shapes[model.shape]

    def get_by_shape(self, shape):
        return self._shapes[shape]

    def step(self, dt):
        if self.done:
            # stop time
            return
        # count up the playing time
        # we could do this with one simple 
        # minus operation but this is in fact easier 
        # right now and i am lazy
        self._time += dt

        if not self._player:
            raise RuntimeError("player not yet registered")
        self._space.step(dt)
        # remove bodies wich are out of bounds
        for model,controller in self._models:
            mp = model.body.position
            pp = self._player.position
            xoff = abs(mp[0]-pp[0])
            yoff = abs(mp[1]-pp[1])
            # distance between ship and asteroid
            d = math.hypot(xoff,yoff)
            if d > self._bounds:
                controller.delete(model)

    def translate(self):
        gl.glLoadIdentity()
        pos = self._player.position
        x = self._mid[0]-pos[0]
        y = self._mid[1]-pos[1]
        gl.glTranslatef(x, y, 0)

class Model:
    collision_type = None

    def __init__(self):
        if not self.collision_type:
            raise RuntimeError("model without collision type")

class Spaceship(Model):
    """
    Spaceship model
    the 'real' thing, not that image we see ;)
    """
    def __init__(self, pos, mass=10, radius=75, accel=1000, rotaccel=1000):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        # always start at the middle of the screen
        self.body.position = pos
        # this spaceship seems to be long and pointy
        # but is in fact a circle ;)
        self.shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self.shape.collision_type = self.collision_type
        # acceleration per second
        self._accel = accel
        # rotational acceleration per second
        self._rotaccel = rotaccel
        # rotation offset (how the spaceship diverges from the view)
        self._rotoff = -math.pi/4

    def accelerate(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._accel))

    def rotate_left(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._rotaccel), (150,0))

    def rotate_right(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._rotaccel), (-150,0))


class Bullet(Model):
    """
    Model of a Bullet
    """
    def __init__(self, pos, angle, mass=0.1, radius=1, force=1000):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        # the position gets calculated in the controll
        # because the spaceship turns
        self.body.position = pos
        # shape is a pretty little circle
        self.shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self.shape.collision_type = self.collision_type
        # rotate the bullet
        self.body.angle = angle
        # shoot the bullet
        self.body.apply_impulse_at_local_point((0,force))

class Player:
    """
    Player controlled Spaceship :)

    bps: bullets per second
    """

    def __init__(self, world, bps=4):
        self._world = world
        # controll  state
        self._rot_left = False
        self._rot_right = False
        self._shoots = False
        self._accels = False

        # this is a spaceship model
        # start in the middle of the screen
        self._spaceship = Spaceship((0,0))
        # add spaceship to the world
        self._world.add(self._spaceship, self)
        # the spaceship has two views
        # the normal view and when it is accelerated
        self._ship_view = SpriteView("images/spaceship.png")
        self._ship_accel = SpriteView("images/spaceship_thrust.png")
        # ship is currently unaccelerated
        self._ship_view.register(self._spaceship)

        # register for bullets
        self._bullets = []
        # we want to see the bullets
        self._bullet_view = SpriteView("images/bullet.png")
        # time between bullets
        self._bps = 1/bps
        # time sind last bullet
        self._tsb = 0

    def delete(self, model):
        if type(model) is Bullet:
            self._bullet_view.remove(model)
            self._world.remove(model, self)

    @property
    def position(self):
        return tuple(self._spaceship.body.position)

    def on_key_press(self, symbol, modifiers):
        """
        handles key press event from window
        """
        if symbol == key.LEFT:
            self._rot_left = True
        elif symbol == key.RIGHT:
            self._rot_right = True
        elif symbol == key.SPACE:
            self._shoots = True
        elif symbol == key.UP:
            if not self._accels:
                try:
                    self._ship_view.remove(self._spaceship)
                    self._ship_accel.register(self._spaceship)
                except KeyError:
                    pass
            self._accels = True


    def on_key_release(self, symbol, modifiers):
        """
        handles key release event from window
        """
        if symbol == key.LEFT:
            self._rot_left = False
        elif symbol == key.RIGHT:
            self._rot_right = False
        elif symbol == key.SPACE:
            self._shoots = False
        elif symbol == key.UP:
            if self._accels:
                try:
                    self._ship_accel.remove(self._spaceship)
                    self._ship_view.register(self._spaceship)
                except KeyError:
                    pass
            self._accels = False

    def _create_bullet(self, dt):
        self._tsb += dt
        if self._tsb < self._bps:
            return
        self._tsb = 0
        # create a bullet
        a = self._spaceship.body.angle
        d = 80
        shippos = self._spaceship.body.position
        # dirty coding here xD
        # i know there is this offset
        # i probably would need to rotate the image
        # and apply force from another side ... T_T
        rot_offset = math.pi/2
        x = math.cos(a+rot_offset)*d + shippos.x
        y = math.sin(a+rot_offset)*d + shippos.y
        bullet = Bullet((x,y), a, force=100)
        self._bullet_view.register(bullet)
        self._world.add(bullet, self)


    def step(self, dt):
        """
        shall be called by the scheduler in an interval
        dt: delta time since last call
        """
        if self._accels:
            self._spaceship.accelerate(dt)
        if self._rot_left:
            self._spaceship.rotate_left(dt)
        if self._rot_right:
            self._spaceship.rotate_right(dt)
        if self._shoots:
            self._create_bullet(dt)

class Asteroid(Model):
    """
    Asteroid model
    the 'real' thing ;)
    """
    def __init__(self, pos, force, mass=10, radius=75):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        self.body.position = pos
        self.shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self.shape.collision_type = self.collision_type
        self.body.apply_impulse_at_local_point(*force)
    

class AsteroidSpammer:
    """
    the Asteroid Controller
    the main objective of an asteroid spammer
    is to spam asteroids ;)

    world: pymunk world model
    screen_size: size of the window in pixels
    player: player controller (for the coordinate of the player)
    screen_offset: the circle where to create asteroids
    max_accel: maximum initial asteroid acceleration
    max_rot: offset for where to apply the initial force on the asteroid
    aps: asteroids per second (how many asteroids per second to spam ~)
    """
    def __init__(self, world, screen_size, player, screen_offset=150, max_accel=5000, max_rot=150, aps=3):
        self._world = world
        self._player = player
        # circle around the screen
        # where asteroids may be created
        self._radius = math.hypot(*screen_size)/2+screen_offset
        # limitation for asteroids to exist
        self._outer_r = self._radius + screen_offset
        # for every asteroid we need to generate
        # a force and rotation
        self._max_accel = max_accel
        self._max_rot = max_rot
        # time between asteroids
        self._aps = 1/aps
        self._last_asteroid = 0
        # asteroids register and view
        self._asteroids = []
        self._asteroid_view = SpriteView("images/asteroid.png")

    def _create_asteroid(self):
        # direction from the ship, where
        # the new asteroid becomes created
        angle = random.uniform(0, math.pi*2)
        off = self._player.position
        # position the asteroid becomes created
        x = math.cos(angle) * self._radius + off[0]
        y = math.sin(angle) * self._radius + off[1]
        # direction where the asteroid is heading to
        # we invert the angle and add a little offset
        hpi = math.pi/2
        direction = -angle + random.uniform(-hpi, hpi)
        # now we need to apply a force at a point of the asteroid
        force = random.uniform(0, self._max_accel)
        hmr = self._max_rot / 2
        offset = random.uniform(-hmr, hmr)
        # create the asteroid
        # (we don't need to know about it after because we don't do anything with it atm)
        asteroid = Asteroid((x,y), [(0,force), (offset,0)])
        # add asteroid to the world
        self._world.add(asteroid, self)
        # register the asteroid
        self._asteroids.append(asteroid)
        # make asteroid visible
        self._asteroid_view.register(asteroid)

    def step(self, dt):
        # create new asteroids if it is time
        self._last_asteroid += dt
        if self._last_asteroid < self._aps:
            return
        self._last_asteroid = 0
        self._create_asteroid()

    def delete(self, model):
        self._world.remove(model, self)
        self._asteroids.remove(model)
        self._asteroid_view.remove(model)

class View:
    """
    register for all the views
    makes drawing really easy
    """
    _view_register = []

    def __init__(self):
        self._view_register.append(self)

    @classmethod
    def draw(self):
        for view in self._view_register:
            view.draw()

class SpriteView(View):
    def __init__(self, img_path):
        View.__init__(self)
        self._image = pyglet.image.load(img_path)
        self._image.anchor_x = self._image.width//2
        self._image.anchor_y = self._image.height//2
        self._model_map = {}
        self._batch = Batch()

    def register(self, model):
        x,y = model.body.position
        self._model_map[model] = Sprite(self._image, x, y, batch=self._batch)

    def remove(self, model):
        self._model_map[model].delete()
        del self._model_map[model]

    def draw(self):
        for m,s in self._model_map.items():
            x,y = m.body.position
            s.update(x=x, y=y, rotation=-m.body.angle/math.pi*180)
        self._batch.draw()

class ScoreView:
    """
    the score view is a little different than
    the other views, because i want a little more
    controll over where it is and when it is drawn
    """
    def __init__(self, screen_size):
        self._x = screen_size[0]/2
        self._y = screen_size[1]/2
        self._label = None
        self._time = time.time()

    def show_score(self):
        duration = int(time.time() - self._time)
        text = "You survived for {} seconds".format(duration)
        self._label = pyglet.text.Label(
            text, 
            font_size=36,
            x=self._x,
            y=self._y,
            anchor_x='center',
            anchor_y='center')

    def draw(self):
        if self._label:
            gl.glLoadIdentity()
            self._label.draw()

if __name__ == "__main__":
    main()
