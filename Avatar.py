from typing import Dict
from direct.actor.Actor import Actor
from panda3d.core import CompassEffect

cam_pivot_z_value: float = 3.0
cam_distance: float = 20.0
mouse_tolerance: float = .005

ralph: str = "./models/ralph.egg"
ralph_animations: Dict[str, str] = {"idle": "./models/ralph-idle",
                                    "walk": "./models/ralph-walk",
                                    "run": "./models/ralph-run"}


class Avatar(Actor):

    # noinspection PyArgumentList
    def __init__(self, game_base, model=ralph, animation_dict=ralph_animations):
        """

        :param game_base: direct.showbase.ShowBase.ShowBase
        :param model: str
        :param animation_dict: {str: str}
        """

        super().__init__(model, animation_dict)

        self.__mouse_watcher_node = game_base.mouseWatcherNode  # gets the mouse watcher from game_base
        self.__win = game_base.win  # gets the window from the game_base
        self.__task_manager = game_base.taskMgr  # gets the task manager

        self.__cam_pivot = self.attachNewNode("camera-pivot-point")  # adds a point for the camera to rotate around
        self.__cam_pivot.setZ(cam_pivot_z_value)  # sets the height of the point
        self.__cam_pivot.setEffect(CompassEffect.make(game_base.render))  # makes the pivot ignore the avatar rotations

        game_base.cam.reparentTo(self.__cam_pivot)  # attach the camera to the node
        game_base.cam.setY(-cam_distance)  # moves the camera back so avatar is visible

        self.__task_manager.add(self.__cam_rotation_task, "camera_rotation_task")

        pass

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
            """
            checks if the cursor is far enough from the center, or in some cases (possibly when the window gets resized)
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

    pass


if __name__ == "__main__":  # for testing and example
    from direct.showbase.ShowBase import ShowBase

    base = ShowBase()
    avatar = Avatar(base)
    avatar.reparentTo(base.render)

    ground = base.loader.loadModel("./models/world.egg")
    ground.reparentTo(base.render)
    base.run()
    pass
