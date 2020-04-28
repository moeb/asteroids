#!/usr/bin/env python3.6

import math

import pymunk
import pyglet
from pyglet import gl
from pyglet.window import key
from pyglet.graphics import Batch, TextureGroup

def main():
    # the entry point of the game
    # look at this if you want to understand
    # the game

    width = 1024
    height = 768
    # create a window; opengl context inclusive
    window = pyglet.window.Window(width, height);

    # create the world space
    # (this part belongs/is to the model)
    world = pymunk.Space()
    # there is no gravity in space
    # (most probably unneeded)
    world.gravity = (0.0, 0.0);


    # this is a spaceship model wich is not yet controlled
    spaceship = Spaceship(world, width, height)
    # the spaceship has two views
    # the normal view and when it is accelerated
    ship_view = SpriteView("images/spaceship.png")
    ship_accel = SpriteView("images/spaceship_thrust.png")

    # the player controls if the spaceship is accelerating or not
    # so it has to change how the ship is shown
    player = Player(spaceship, ship_view, ship_accel)
    # the player is an event-handler for the Window class of pyglet
    # where it gets it's keyboard events
    window.push_handlers(player)

    # the other controller is the AsteroidSpammer
    # whose task is to spam Asteroids
    #asteroid_spammer = AsteroidSpammer(world)

    # the window controls when it is drawn
    @window.event
    def on_draw():
        window.clear()
        # every view is registered with View
        # so View.draw draws everything
        View.draw()

    # everything that needs to be done continually
    # has to be in this function
    def interval_cb(dt):
        # world time has to go on
        world.step(dt)
        # controll of the ship is in world time
        player.control_ship(dt)
    # now schedule the callback ~30 times per second
    pyglet.clock.schedule_interval(interval_cb, 1/30)

    # finally we are done :)
    # lets run the app
    pyglet.app.run()


class Spaceship:
    """
    Spaceship model
    the 'real' thing, not that image we see ;)
    """
    def __init__(self, world, width, height, mass=10, radius=75, accel=100000, rotaccel=100):
        self.world = world
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        # always start at the middle of the screen
        self.body.position = (width/2, height/2)
        # this spaceship seems to be long and pointy
        # but is in fact a circle ;)
        self.shape = pymunk.Circle(self.body, radius)
        # add spaceship to the world
        self.world.add(self.body, self.shape)
        # acceleration per second
        self._accel = accel
        # rotational acceleration per second
        self._rotaccel = rotaccel

    def remove(self):
        self.world.remove(self.body)

    def accelerate(self, dt):
        f = dt * self._accel
        x = math.cos(self.body.angle)*f
        y = math.sin(self.body.angle)*f
        self.body.apply_force_at_local_point((x,y),(0,0))

    def rotate_left(self, dt):
        self.body.angle -= dt*self._rotaccel

    def rotate_right(self, dt):
        self.body.angle += dt*self._rotaccel

class Player:
    """
    Player controlled Spaceship :)
    """

    def __init__(self, spaceship, ship_view, ship_accel):
        # controll  state
        self._rot_left = False
        self._rot_right = False
        self._shoots = False
        self._accels = False

        # spaceship model
        self._spaceship = spaceship
        # normal view of the spaceship
        self._ship_view = ship_view
        # view of spaceship while accelerating
        self._ship_accel = ship_accel
        # ship is currently unaccelerated
        self._ship_view.register(self._spaceship)


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

    def control_ship(self, dt):
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
        self._batch = Batch()
        self._image = pyglet.image.load(img_path)
        self._texture = self._image.get_texture()
        self._group = TextureGroup(self._texture)
        self._model_map = {}
       
        # size of quad without rotation
        self._r = self._image.width/2
        self._l = -self._r
        self._t = self._image.height/2
        self._b = -self._t

    def _calculate_quad(self, model):
        """
        better do this than draw every
        rotated sprite alone

        can be further optimized with a shader
        """
        # TODO: fix rotation !
        angle = model.body.angle
        x = model.body.position.x
        y = model.body.position.y
        cos = math.cos(angle)
        sin = math.sin(angle)
        cl = cos * self._l
        sl = sin * self._l
        cb = cos * self._b
        sb = sin * self._b
        cr = cos * self._r
        sr = sin * self._r
        ct = cos * self._t
        st = sin * self._t
        return (
            cl-sb+x, sl-cb+y,
            cr-sb+x, sr-cb+y,
            cr-st+x, sr-ct+y,
            cl-st+x, st-ct+y
        )

    def register(self, model):
        self._model_map[model] = self._batch.add(4, gl.GL_QUADS, self._group,
                                                 ('v2f/dynamic', [0]*8),
                                                 ('t2f/static', (0, 0, 1, 0, 1, 1, 0, 1)))

    def remove(self, model):
        self._model_map[model].delete()
        del self._model_map[model]

    def draw(self):
        for m,v in self._model_map.items():
            v.vertices = self._calculate_quad(m)
            #print(v.vertices)
        self._batch.draw()


if __name__ == "__main__":
    main()
