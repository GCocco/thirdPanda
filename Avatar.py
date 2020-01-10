import typing
from direct.actor.Actor import Actor
from panda3d.core import CompassEffect, ClockObject, Point3
from panda3d.core import CollisionBox, CollisionSegment, CollisionNode, CollisionRay
from panda3d.core import CollisionHandlerPusher, CollisionHandlerQueue, CollisionTraverser


cam_pivot_z_value: float = 3.0
cam_distance: float = 20.0
mouse_tolerance: float = .05

ralph: str = "./models/ralph.egg"
ralph_animations: typing.Dict[str, str] = {"idle": "./models/ralph-idle",
                                           "walk": "./models/ralph-walk",
                                           "run": "./models/ralph-run",
                                           "fall": "./models/ralph-fall"}

angles_map = {(True, False, False, False): 180,  # gets the angle of the avatar based on pressed keys
              (False, True, False, False): 90,  # invalid combinations of keys are ignored
              (False, False, True, False): 0,
              (False, False, False, True): -90,
              (True, True, False, False): 135,
              (True, False, False, True): -135,
              (False, True, True, False): 45,
              (False, False, True, True): -45}

fixed_update_delta: float = .01

walk_speed: float = -20
run_speed: float = -30

collider_x = 1
collider_y = 1
collider_bottom = 1
collider_top = 5

climb_threshold = 1
fall_speed = 15

jump_time = 1
jump_speed = 10


class Avatar(Actor):

    def __get_closest_entry(entries, node):
        res = None
        try:
            res = entries[0].getSurfacePoint(node)[2]
            pass
        except IndexError:
            return res

        for n3 in entries:
            if n3.getSurfacePoint(node)[2] > res:
                res = n3.getSurfacePoint(node)[2]
                pass
            pass
        return res

    def __init__(self, game_base, model=ralph, animation_dict=None):
        """


        :param game_base: direct.showbase.ShowBase.ShowBase
        :param model: str
        :param animation_dict: typing.Dict[str: str]
        """
        if animation_dict is None:
            animation_dict = ralph_animations
            pass

        super().__init__(model, animation_dict)
        self.__task_manager = game_base.taskMgr  # gets the task manager

        """camera controls section"""
        self.__mouse_watcher_node = game_base.mouseWatcherNode  # gets the mouse watcher from game_base
        self.__win = game_base.win  # gets the window from the game_base

        self.__skip_frame = False   # a bool to skip a frame when returning from a pause.
        # this variable is needed since the cursor is moved to the given position in the next frame.

        self.__cam_pivot = self.attachNewNode("camera-pivot-point")  # adds a point for the camera to rotate around
        self.__cam_pivot.setZ(cam_pivot_z_value)  # sets the height of the point
        self.__cam_pivot.setEffect(CompassEffect.make(game_base.render))  # makes the pivot ignore the avatar rotations

        game_base.cam.reparentTo(self.__cam_pivot)  # attach the camera to the node
        game_base.cam.setY(-cam_distance)  # moves the camera back so avatar is visible

        """avatar movement section"""
        self.__global_clock = ClockObject.getGlobalClock()
        self.__key_map = {"w": False,  # a dictionary to keep track of the pressed movement buttons
                          "a": False,
                          "s": False,
                          "d": False,
                          "shift": False}

        # when a movement button is pressed, changes it's value to True in the keymap

        self.accept("w", self.__set_key, ["w", True])
        self.accept("a", self.__set_key, ["a", True])
        self.accept("s", self.__set_key, ["s", True])
        self.accept("d", self.__set_key, ["d", True])
        self.accept("shift", self.__set_key, ["shift", True])
        self.accept("shift-w", self.__set_key, ["w", True])
        self.accept("shift-a", self.__set_key, ["a", True])
        self.accept("shift-s", self.__set_key, ["s", True])
        self.accept("shift-d", self.__set_key, ["d", True])
        self.accept("shift", self.__set_key, ["shift", True])
        self.accept("w-up", self.__set_key, ["w", False])
        self.accept("a-up", self.__set_key, ["a", False])
        self.accept("s-up", self.__set_key, ["s", False])
        self.accept("d-up", self.__set_key, ["d", False])
        self.accept("shift-up", self.__set_key, ["shift", False])

        """animation section"""

        self.__blend_map = {animation_name: .0 for animation_name in animation_dict}

        self.enableBlend()
        self.loop("idle")
        self.__current_animation = "idle"
        self.__prev_animation = None
        self.play_char()

        """collisions section"""
        self.__player_collider = self.attachNewNode(CollisionNode("player-collider"))
        self.__player_collider.node().addSolid(CollisionBox(Point3(collider_x, collider_y, collider_bottom),
                                                            Point3(-collider_x, -collider_y, collider_top)))

        pusher = CollisionHandlerPusher()
        pusher.addCollider(self.__player_collider, self)

        # base cTrav may not be instantiated, may need to do it here
        try:
            base.cTrav.addCollider(pusher, self.__collider_handler)
            pass
        except AttributeError:
            print("warning (Avatar): base.cTrav is not instantiated yet. Consider doing it before creating a Avatar")
            base.cTrav = CollisionTraverser()
            base.cTrav.addCollider(self.__player_collider, pusher)
            pass
        pass

        """the character needs something that pushes him to the ground.
           this won't be simulated gravity force since speed is gonna be constant"""

        self.__ground_pusher = self.attachNewNode(CollisionNode("ground-pusher"))

        self.__ground_pusher.node().addSolid(CollisionRay(0, 0, collider_bottom, 0, 0, -1))

        self.__ground_handler = CollisionHandlerQueue()
        self.__ground_pusher.show()
        self.__ground_pusher.node().setIntoCollideMask(0b0)
        base.cTrav.addCollider(self.__ground_pusher, self.__ground_handler)
        self.__task_manager.add(self.__ground_task, "ground-task")

        """fall animation section, also used for jumping"""
        self.__is_grounded = True

        """jumping"""
        self.accept("space", self.__jump)
        self.accept("shift-space", self.__jump)

    def __set_key(self, key, value):
        """
        Updates the element in the key map for the given key to the given value

        :param key: str the key which value is getting updated
        :param value: bool the value assigned to the key
        :return: None
        """

        self.__key_map[key] = value
        return

    def __cam_rotation_task(self, task):
        """
        the task in charge of rotating the camera relatively to the mouse movement

        :param task: direct.task.Task panda assigned Task obj
        :return: Task.cont
        """
        if self.__mouse_watcher_node.hasMouse():
            props = self.__win.getProperties()
            x = self.__mouse_watcher_node.getMouseX() * 20  # gets x and y coordinates of cursor
            y = self.__mouse_watcher_node.getMouseY() * 20
            self.__win.movePointer(0,  # moves cursor to the center
                                   int(props.getXSize() / 2),
                                   int(props.getYSize() / 2))

            """when returning from a pause, the cursor may not be in the center of the window.
               to avoid moving the camera when returning to play, is necessary to skip a frame.
            """
            if self.__skip_frame:
                self.__skip_frame = False
                return task.cont

            """
            checks if the cursor is far enough from the center, or in some cases (usually when the window gets resized)
            the camera may move even if the cursor doesn't. Then rotates the camera pivot node based on the coordinates
            """

            if abs(x) > mouse_tolerance:
                self.__cam_pivot.setH(self.__cam_pivot.getH() - x * 10)  # Z axis rotation (Heading)
                pass

            """also checks if the angle doesn't put the camera upside down"""
            if (y > mouse_tolerance and self.__cam_pivot.getP() < 70) or (
                    y < -mouse_tolerance and self.__cam_pivot.getP() > -70):
                self.__cam_pivot.setP(self.__cam_pivot.getP() + y * 10)  # X axis rotation (Pitch)
                pass
            pass

        return task.cont

    def __movement_task(self, task):
        """

        :param task: direct.task.Task panda assigned Task obj
        :return: Task.cont
        """

        # gets the angle for the pressed keys combination
        angle = angles_map.get((self.__key_map["w"], self.__key_map["a"], self.__key_map["s"], self.__key_map["d"]))

        if angle is not None:                            # if the combination of keys is valid
            self.setH(self.__cam_pivot.getH() - angle)   # rotates the avatar the given value relatively to the camera
            if self.__key_map["shift"]:                  # if shift is pressed (run)
                self.setY(self, run_speed * self.__global_clock.getDt())
                if self.__is_grounded:
                    self.set_animation("run")
                    pass
                else:
                    self.set_animation("fall")
                    pass
                pass
            else:
                self.setY(self, walk_speed * self.__global_clock.getDt())
                if self.__is_grounded:
                    self.set_animation("walk")
                    pass
                else:
                    self.set_animation("fall")
                    pass
                pass
            pass
        else:
            if self.__is_grounded:
                self.set_animation("idle")
                pass
            else:
                self.set_animation("fall")
                pass
            pass
        return task.cont

    def __blend_task(self, task):
        """

        :param task: direct.task.Task panda assigned Task obj
        :return: Task.cont
        """
        for animation in self.__blend_map:
            if animation == self.__current_animation and self.__blend_map[animation] < 1.0:
                self.__blend_map[animation] += .1
                pass

            elif animation != self.__current_animation and self.__blend_map[animation] > 0.1:
                self.__blend_map[animation] -= .1
                pass

            self.setControlEffect(animation, self.__blend_map[animation])

            if self.__blend_map[animation] < .0:
                self.getAnimControl(animation).stop()
                pass
            pass

        return task.cont

    def set_animation(self, animation):
        """

        :param animation: str the animation name
        :return:
        """
        if self.__prev_animation != animation:
            self.loop(animation)
            self.__prev_animation = self.__current_animation
            self.__current_animation = animation
            pass
        return

    def __ground_task(self, task):
        entries = list(self.__ground_handler.getEntries())

        z = Avatar.__get_closest_entry(self.__ground_handler.getEntries(), self)

        if z is None:
            return task.cont
        if z < -climb_threshold:
            self.setZ(self, -fall_speed * self.__global_clock.getDt())
            self.__is_grounded = False
            pass
        elif z < climb_threshold * -.08:
            self.setZ(self, -fall_speed * self.__global_clock.getDt())
            self.__is_grounded = True
            pass
        return task.cont

    def play_char(self):
        self.__skip_frame = True
        self.__task_manager.add(self.__cam_rotation_task, "camera_rotation_task")
        self.__task_manager.add(self.__movement_task, "movement_task")
        self.__task_manager.add(self.__blend_task, "animation_blend")
        self.acceptOnce("escape", self.stop_char)
        return

    def stop_char(self):
        self.__task_manager.remove("camera_rotation_task")
        self.__task_manager.remove("movement_task")
        self.set_animation("idle")

        self.acceptOnce("escape", self.play_char)
        return

    def __jump_task(self, task):
        self.setZ(self, jump_speed * self.__global_clock.getDt())
        return task.cont

    def __end_jump(self):
        self.__task_manager.remove("jumping")
        self.__task_manager.add(self.__ground_task, "ground-task")
        return

    def __jump(self):
        if self.__is_grounded:
            self.__is_grounded = False
            self.__task_manager.remove("ground-task")  # remove the ground task, or the avatar gets pushed down
            self.__task_manager.add(self.__jump_task, "jumping")
            self.__task_manager.doMethodLater(jump_time, self.__end_jump, "end-jump", extraArgs=[])
            pass
        return

    pass


if __name__ == "__main__":  # for testing and example
    from direct.showbase.ShowBase import ShowBase

    base = ShowBase()
    base.cTrav = CollisionTraverser
    avatar = Avatar(base)
    avatar.reparentTo(base.render)

    ground = base.loader.loadModel("./models/world.egg")
    ground.reparentTo(base.render)
    avatar.setZ(5)

    base.run()
    pass
