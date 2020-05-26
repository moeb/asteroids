#!/usr/bin/env python3

import math
import time
import random

from abc import ABC, abstractmethod, abstractproperty

import pymunk
import pyglet
from pyglet import gl
from pyglet.window import key
from pyglet.graphics import Batch
from pyglet.graphics import OrderedGroup
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

    # handlesthe displaying of images and text
    view = View()

    # create the world space
    world = World(win_size, bounds, view)

    # register models
    world.register_model(Asteroid)
    world.register_model(Bullet)
    world.register_model(Spaceship)

    # the player controls a spaceship
    player = Player(world, win_size, view)
    # the player is an event-handler for the Window class of pyglet
    # where it gets it's keyboard events
    window.push_handlers(player)

    # the other controller is the AsteroidSpammer
    # whose task is to spam Asteroids
    asteroid_spammer = AsteroidSpammer(world, win_size, view)

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
                pass
        return False

    @world.collision_handler(Spaceship, Asteroid)
    def post_solve(arbiter, space, data):
        try:
            for shape in arbiter.shapes:
                model, controller = world.get_by_shape(shape)
                # stop game
                world.done = True
        except KeyError:
            pass

    # the window controls when it is drawn
    @window.event
    def on_draw():
        window.clear()
        # every view is registered with View
        # so View.draw draws everything
        view.draw()

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


class Model(ABC):
    
    @property
    def collision_type(self):
        if not self._collision_type:
            raise RuntimeError("Model has not been registered with World")
        return self._collision_type

    @abstractproperty
    def body(self):
        pass

    @abstractproperty
    def shape(self):
        pass


class Controller(ABC):

    @abstractmethod
    def step(self, dt):
        pass

    @abstractmethod
    def delete(self, model):
        pass


class World:
    """
    world model
    ever object must be registered with world
    
    world is responsible for removing out of bounds objects
    and progressing pymunk time

    dispatches events for collision handling
    """
    def __init__(self, window_size, bounds, view):
        self._time = time.time()
        self._space = pymunk.Space()
        self._space.gravity = (0, 0)
        self._models = []
        self._shapes = {}

        # bounds within objects may exist
        self._left = -bounds
        self._right = window_size[0]+bounds
        self._bottom = -bounds
        self._top = window_size[1]+bounds

        self._mid = (window_size[0]/2, window_size[1]/2)
        self._collision_handlers = {}
        # when the game is done
        # switch this boolean
        self._done = False
        # world needs the view to display
        # the score at the end of the game
        self._view = view

    @property
    def done(self):
        return self._done

    @done.setter
    def done(self, done):
        if self._done:
            return
        sec = int(time.time()-self._time)
        text = "You stayed alive for {} seconds".format(sec)
        self._view.create_label(text, x=self._mid[0], y=self._mid[1],
                                anchor_x="center", anchor_y="center")
        self._done = done

    def register_model(self, model_type):
        if model_type not in self._collision_handlers:
            self._collision_handlers[model_type] = len(self._collision_handlers)+1
            model_type.collision_type = len(self._collision_handlers)

    def collision_handler(self, m1, m2):
        """
        decorator for registering a collision handler
        @world.collision_handler(Asteroid, Bullet)
        def pre_solve(arbiter, space, data):
            do_stuff()

        allowed function names are:
            pre_solve
            post_solve
            begin
            separate

        the function is expected to accept 3 inputs
        namely: arbiter, space and data
        """
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

    def _delete_out_of_bounds(self):
        # remove bodies wich are out of bounds
        for model,controller in self._models:
            x,y = model.body.position
            if (x < self._left or x > self._right or \
                y < self._bottom or y > self._top):
                if type(model) == Spaceship:
                    self.done = True
                else: controller.delete(model)

    def step(self, dt):
        if self.done:
            # stop time
            return
        self._space.step(dt)
        self._delete_out_of_bounds()


class Spaceship(Model):
    """
    Spaceship model
    the 'real' thing, not that image we see ;)
    """
    def __init__(self, pos, mass=10, radius=40, accel=1000, rotaccel=125):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self._body = pymunk.Body(mass, moment)
        # always start at the middle of the screen
        self._body.position = pos
        # this spaceship seems to be long and pointy
        # but is in fact a circle ;)
        self._shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self._shape.collision_type = self.collision_type
        # acceleration per second
        self._accel = accel
        # rotational acceleration per second
        self._rotaccel = rotaccel
        # rotation offset (how the spaceship diverges from the view)
        self._rotoff = -math.pi/4

    @property
    def body(self):
        return self._body

    @property
    def shape(self):
        return self._shape

    def accelerate(self, dt):
        self._body.apply_impulse_at_local_point((0,dt*self._accel))

    def rotate_left(self, dt):
        self._body.apply_impulse_at_local_point((0,dt*self._rotaccel), (150,0))

    def rotate_right(self, dt):
        self._body.apply_impulse_at_local_point((0,dt*self._rotaccel), (-150,0))


class Bullet(Model):
    """
    Model of a Bullet
    """
    def __init__(self, pos, angle, mass=0.1, radius=1, force=1000):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self._body = pymunk.Body(mass, moment)
        # the position gets calculated in the controll
        # because the spaceship turns
        self._body.position = pos
        # shape is a pretty little circle
        self._shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self._shape.collision_type = self.collision_type
        # rotate the bullet
        self._body.angle = angle
        # shoot the bullet
        self._body.apply_impulse_at_local_point((0,force))

    @property
    def body(self):
        return self._body

    @property
    def shape(self):
        return self._shape

class Player(Controller):
    """
    Player controlled Spaceship :)

    bps: bullets per second
    """

    def __init__(self, world, win_size, view, bps=6):
        Controller.__init__(self)
        self._world = world
        self._view = view
        # controll  state
        self._rot_left = False
        self._rot_right = False
        self._shoots = False
        self._accels = False

        # this is a spaceship model
        # start in the middle of the screen
        w, h = win_size
        self._spaceship = Spaceship((w/2, h/2), radius=30)
        # add spaceship to the world
        self._world.add(self._spaceship, self)
        # the spaceship has two views
        # the normal view and when it is accelerated
        self._ship_view = "images/spaceship.png"
        self._ship_accel = "images/spaceship_thrust.png"
        # the scale is the same for ship_view and accel_view
        self._scale = 0.5
        # the zindex is the same too
        self._zindex = 3
        # ship is currently unaccelerated
        self._view.register_model(self._spaceship, self._ship_view,
                                  scale=self._scale, zindex=self._zindex)

        # register for bullets
        self._bullets = []
        # we want to see the bullets
        self._bullet_view = "images/bullet.png"
        # time between bullets
        self._bps = 1/bps
        # time sind last bullet
        self._tsb = 0

    def delete(self, model):
        if type(model) is Bullet:
            self._view.remove_model(model)
            self._world.remove(model, self)

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
                    self._view.remove_model(self._spaceship)
                    self._view.register_model(self._spaceship, self._ship_accel,
                                              scale=self._scale, zindex=self._zindex)
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
                    self._view.remove_model(self._spaceship)
                    self._view.register_model(self._spaceship, self._ship_view,
                                              scale=self._scale, zindex=self._zindex)
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
        self._view.register_model(bullet, self._bullet_view)
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
    def __init__(self, pos, force, mass=10, radius=40):
        Model.__init__(self)
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self._body = pymunk.Body(mass, moment)
        self._body.position = pos
        self._shape = pymunk.Circle(self.body, radius)
        # register collision handler
        self._shape.collision_type = self.collision_type
        self._body.apply_impulse_at_local_point(*force)
   
    @property
    def body(self):
        return self._body

    @property
    def shape(self):
        return self._shape


class AsteroidSpammer(Controller):
    """
    the Asteroid Controller
    the main objective of an asteroid spammer
    is to spam asteroids ;)

    world: pymunk world model
    screen_size: size of the window in pixels
    screen_offset: the circle where to create asteroids
    max_accel: maximum initial asteroid acceleration
    max_rot: offset for where to apply the initial force on the asteroid
    aps: asteroids per second (how many asteroids per second to spam ~)
    """
    def __init__(self, world, screen_size, view, screen_offset=150, max_accel=2500, max_rot=150, aps=3):
        Controller.__init__(self)
        self._world = world
        self._view = view
        # circle around the screen
        # where asteroids may be created
        self._radius = math.hypot(*screen_size)/2+screen_offset
        # limitation for asteroids to exist
        self._outer_r = self._radius + screen_offset
        # mid of the screeen
        self._mid = screen_size[0]/2, screen_size[1]/2
        # for every asteroid we need to generate
        # a force and rotation
        self._max_accel = max_accel
        self._max_rot = max_rot
        # time between asteroids
        self._aps = 1/aps
        self._last_asteroid = 0
        # asteroids register and view
        self._asteroids = []
        self._asteroid_view = "images/asteroid.png"
        self._scale = 0.6
        self._zindex = 2

    def _create_asteroid(self):
        # direction from the ship, where
        # the new asteroid becomes created
        angle = random.uniform(0, math.pi*2)
        # position the asteroid becomes created
        x = math.cos(angle) * self._radius + self._mid[0]
        y = math.sin(angle) * self._radius + self._mid[1]
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
        self._view.register_model(asteroid, self._asteroid_view,
                                  scale=self._scale, zindex=self._zindex)

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
        self._view.remove_model(model)
        # we could spawn smaller asteroids here :)

class View:
    """
    handles everything graphical
    """

    def __init__(self):
        # map of all loaded and modified images
        self._image_map = {}
        # maps models to sprites for updating
        self._model2sprite = {}
        # groups for drawing order
        self._draw_groups = {}
        # we only need one batch
        self._batch = Batch()

    def _get_group(self, zindex):
        """
        zindex: drawing order within batch
        """
        # zindex must be an integer
        assert type(zindex) is int
        # create group if it does not exist
        if zindex not in self._draw_groups:
            self._draw_groups[zindex] = OrderedGroup(zindex)
        return self._draw_groups[zindex]

    def _get_img(self, path):
        """
        path: path to image
        """
        # create image if it does not exist
        if path not in self._image_map:
            img = pyglet.image.load(path)
            img.anchor_x = img.width//2
            img.anchor_y = img.height//2
            self._image_map[path] = img
        return self._image_map[path]

    def register_model(self, model, path, scale=1.0, zindex=1):
        """
        model: the model behind the image
        path: path to the image
        scale: scale of the image
        zindex: lower is drawn in the back higher in the front
        """
        # position of model is the position of the image
        x,y = model.body.position
        img = self._get_img(path)
        group = self._get_group(zindex)
        sprite = Sprite(img, x, y, group=group, batch=self._batch)
        sprite.scale = scale
        self._model2sprite[model] = sprite

    def remove_model(self, model):
        """
        remove sprite registered with model
        """
        self._model2sprite[model].delete()
        del self._model2sprite[model]

    def create_label(self, text, zindex=9, **kwargs):
        """
        creates a text label in the Batch of the View
        text: text wich shall be visualized
        zindex: drawing order
        kwargs: additional parameters for pyglet.text.Label
        -- call delete on the returned label to remove
        -- from batch
        """
        kwargs['text'] = text
        kwargs['group'] = self._get_group(zindex)
        kwargs['batch'] = self._batch
        # the label may be destroyed at the whim of the controller
        return pyglet.text.Label(**kwargs)

    def _update_models(self):
        # update sprites with new positional and rotational data
        for m,s in self._model2sprite.items():
            x,y = m.body.position
            s.update(x=x, y=y, rotation=-m.body.angle/math.pi*180)

    def draw(self):
        self._update_models()
        self._batch.draw()




if __name__ == "__main__":
    main()
