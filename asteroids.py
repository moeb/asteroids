#!/usr/bin/env python3.6

import math

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
    # create a window; opengl context inclusive
    window = pyglet.window.Window(width, height);

    # create the world space
    # (this part belongs/is to the model)
    world = pymunk.Space()
    # there is no gravity in space
    # (most probably unneeded)
    world.gravity = (0.0, 0.0);

    # mid of the screen
    mid = (width/2, height/2)
    # the player controlls a spaceship
    player = Player(world)
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
        # move world space, so the spaceship is in the middle
        gl.glLoadIdentity()
        pos = player.position
        x = mid[0]-pos[0]
        y = mid[1]-pos[1]
        z = 0
        print(x,y)
        gl.glTranslatef(x, y, z)
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
    def __init__(self, world, pos, mass=10, radius=75, accel=1000, rotaccel=1000):
        self.world = world
        moment = pymunk.moment_for_circle(mass, 0, radius)
        self.body = pymunk.Body(mass, moment)
        # always start at the middle of the screen
        self.body.position = pos
        # this spaceship seems to be long and pointy
        # but is in fact a circle ;)
        self.shape = pymunk.Circle(self.body, radius)
        # add spaceship to the world
        self.world.add(self.body, self.shape)
        # acceleration per second
        self._accel = accel
        # rotational acceleration per second
        self._rotaccel = rotaccel
        # rotation offset (how the spaceship diverges from the view)
        self._rotoff = -math.pi/4

    def remove(self):
        self.world.remove(self.body)

    def accelerate(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._accel))

    def rotate_left(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._rotaccel), (150,0))

    def rotate_right(self, dt):
        self.body.apply_impulse_at_local_point((0,dt*self._rotaccel), (-150,0))

class Player:
    """
    Player controlled Spaceship :)
    """

    def __init__(self, world):
        # controll  state
        self._rot_left = False
        self._rot_right = False
        self._shoots = False
        self._accels = False

        # this is a spaceship model
        # start in the middle of the screen
        self._spaceship = Spaceship(world, (0,0))
        # the spaceship has two views
        # the normal view and when it is accelerated
        self._ship_view = SpriteView("images/spaceship.png")
        self._ship_accel = SpriteView("images/spaceship_thrust.png")
        # ship is currently unaccelerated
        self._ship_view.register(self._spaceship)

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


if __name__ == "__main__":
    main()
