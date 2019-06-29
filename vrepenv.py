import numpy as np
import calculations as cal
import vrep
import time


class ArmEnv(object):
    state_dim = 9  # number of variables that describe the robot
    action_dim = 6  # number of actions that could be taken
    action_bound = cal.action_bound  # boundary of the action out put of RL algorithms

    def __init__(self):

        # vrep init session
        print('Program started')
        vrep.simxFinish(-1)  # just in case, close all opened connections
        # Connect to V-REP, get clientID
        self.clientID = vrep.simxStart('127.0.0.1', 19999, True, True, 5000, 5)  # enter scene ID here

        if self.clientID != -1:  # confirm connection
            print('Connected to remote API server')

        else:
            exit('Failed connecting to remote API server')

        vrep.simxSetIntegerSignal(self.clientID, "Apimode", 1, vrep.simx_opmode_oneshot)  # activate apimode

        # vrep sensor setup

        # Get Joint data
        self.Joints = np.zeros((6, 2))
        self.Joint_boundary = np.zeros((6, 2))
        for i in range(6):
            for j in range(2):
                self.errorCode, self.Joints[i][j] = vrep.simxGetFloatSignal(self.clientID,
                                                                            'Interval_{}_{}'.format(i + 1, j + 1),
                                                                            vrep.simx_opmode_streaming)
                while self.errorCode:
                    self.errorCode, self.Joints[i][j] = vrep.simxGetFloatSignal(self.clientID,
                                                                                'Interval_{}_{}'.format(i + 1, j + 1),
                                                                                vrep.simx_opmode_buffer)
                # print(self.errorCode,'Interval_{}_{}'.format(i+1,j+1),self.Joints[i][j])
            self.Joint_boundary[i] = [(self.Joints[i][0] / np.pi * 180),
                                      ((self.Joints[i][0] / np.pi * 180) + (self.Joints[i][1] / np.pi * 180))]
            print("Joint boundary ", i, self.Joint_boundary[i])

        # Setup controllable variables
        self.movementMode = 1  # work under FK(0) or IK(1)

        self.FK = np.zeros(1, dtype=[('Joint1', np.float32), ('Joint2', np.float32), ('Joint3', np.float32),
                                     ('Joint4', np.float32), ('Joint5', np.float32), ('Joint6', np.float32)])
        # initial angle in FK mode
        self.FK['Joint1'] = 0
        self.FK['Joint2'] = 0
        self.FK['Joint3'] = 0
        self.FK['Joint4'] = 0
        self.FK['Joint5'] = -90
        self.FK['Joint6'] = 0

        self.IK = np.zeros(1, dtype=[('Pos_x', np.float32), ('Pos_y', np.float32), ('Pos_z', np.float32),
                                     ('Alpha', np.float32), ('Beta', np.float32), ('Gamma', np.float32)])
        # initial position in IK mode
        self.IK['Pos_x'] = 0
        self.IK['Pos_y'] = 0
        self.IK['Pos_z'] = 0
        self.IK['Alpha'] = 0
        self.IK['Beta'] = 0
        self.IK['Gamma'] = 0

        # Auxiliary variables

    def step(self, action):
        done = False  # round indicator

        # set FK or IK
        vrep.simxSetIntegerSignal(self.clientID, "movementMode", self.movementMode, vrep.simx_opmode_oneshot)
        # read force sensor
        self.errorCode, self.forceState, self.forceVector, self.torqueVector = \
            vrep.simxReadForceSensor(self.clientID, self.force_sensor_handle, vrep.simx_opmode_buffer)
        self.errorCode, self.position = \
            vrep.simxGetObjectPosition(self.clientID, self.force_sensor_handle, -1, vrep.simx_opmode_buffer)

        # calculations
        # adjust action to usable motion
        action = cal.actions(action, self.movementMode)

        # do action
        self.FK['Joint1'] += action[0]
        self.FK['Joint2'] += action[1]
        self.FK['Joint3'] += action[2]
        self.FK['Joint4'] += action[3]
        self.FK['Joint5'] += action[4]
        self.FK['Joint6'] += action[5]

        # boundary
        self.FK['Joint1'] = np.clip(self.FK['Joint1'], *self.Joint_boundary[0])
        self.FK['Joint2'] = np.clip(self.FK['Joint2'], *self.Joint_boundary[1])
        self.FK['Joint3'] = np.clip(self.FK['Joint3'], *self.Joint_boundary[2])
        self.FK['Joint4'] = np.clip(self.FK['Joint4'], *self.Joint_boundary[3])
        self.FK['Joint5'] = np.clip(self.FK['Joint5'], *self.Joint_boundary[4])
        self.FK['Joint6'] = np.clip(self.FK['Joint6'], *self.Joint_boundary[5])

        # send signal
        vrep.simxSetFloatSignal(self.clientID, "Joint1",
                                (self.FK['Joint1'] * np.pi / 180 - self.Joints[0][0]) / self.Joints[0][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint2",
                                (self.FK['Joint2'] * np.pi / 180 - self.Joints[1][0]) / self.Joints[1][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint3",
                                (self.FK['Joint3'] * np.pi / 180 - self.Joints[2][0]) / self.Joints[2][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint4",
                                (self.FK['Joint4'] * np.pi / 180 - self.Joints[3][0]) / self.Joints[3][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint5",
                                (self.FK['Joint5'] * np.pi / 180 - self.Joints[4][0]) / self.Joints[4][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint6",
                                (self.FK['Joint6'] * np.pi / 180 - self.Joints[5][0]) / self.Joints[5][1] * 1000,
                                vrep.simx_opmode_oneshot)
        time.sleep(0.1)  # wait for action to finish

        # state
        s = np.concatenate((self.position, self.forceVector, self.torqueVector))

        # done and reward
        r, done = cal.reword(s)

        return s, r, done

    def reset(self):

        # read force sensor
        self.errorCode, self.forceState, self.forceVector, self.torqueVector = \
            vrep.simxReadForceSensor(self.clientID, self.force_sensor_handle, vrep.simx_opmode_buffer)
        self.errorCode, self.position = \
            vrep.simxGetObjectPosition(self.clientID, self.force_sensor_handle, -1, vrep.simx_opmode_buffer)

        # reset position
        self.FK['Joint1'] = 0
        self.FK['Joint2'] = 0
        self.FK['Joint3'] = 0
        self.FK['Joint4'] = 0
        self.FK['Joint5'] = -90
        self.FK['Joint6'] = 0
        # send signal
        vrep.simxSetFloatSignal(self.clientID, "Joint1",
                                (self.FK['Joint1'] * np.pi / 180 - self.Joints[0][0]) / self.Joints[0][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint2",
                                (self.FK['Joint2'] * np.pi / 180 - self.Joints[1][0]) / self.Joints[1][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint3",
                                (self.FK['Joint3'] * np.pi / 180 - self.Joints[2][0]) / self.Joints[2][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint4",
                                (self.FK['Joint4'] * np.pi / 180 - self.Joints[3][0]) / self.Joints[3][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint5",
                                (self.FK['Joint5'] * np.pi / 180 - self.Joints[4][0]) / self.Joints[4][1] * 1000,
                                vrep.simx_opmode_oneshot)
        vrep.simxSetFloatSignal(self.clientID, "Joint6",
                                (self.FK['Joint6'] * np.pi / 180 - self.Joints[5][0]) / self.Joints[5][1] * 1000,
                                vrep.simx_opmode_oneshot)
        time.sleep(1)
            # wait for action to finish
        # state
        s = np.concatenate((self.position, self.forceVector, self.torqueVector))
        return s

    @staticmethod
    def sample_action():
        return np.random.rand(6) - 0.5


# input random action to the robot
if __name__ == '__main__':
    env = ArmEnv()
    while True:
        a = env.sample_action() * 100
        env.step(a)
