from asteroids import main, SpriteView


if __name__ == "__main__":
    win,world,ship = main()
    sw = SpriteView("images/spaceship.png")
    sw.register(ship)
    for v in sw.draw():
        print(v.delete)
