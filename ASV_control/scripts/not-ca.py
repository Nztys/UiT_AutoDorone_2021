'''
----------------------------------------------------------
    @file: collision_avoidance.py
    @date: June 10, 2020
    @author: Ivana Collado
    @e-mail: ivanacollado@gmail.com
    @brief: Implementation of collision avoidance algorithm 
    @version: 1.0
    @licence: Open source
----------------------------------------------------------
'''

import math
import os
import sys
import time

import numpy as np
import rospy
from geometry_msgs.msg import Pose2D, Vector3
from std_msgs.msg import Float64,  Float32MultiArray, String
from usv_perception.msg import obstacles_list

# Class definition for easy debugging
class Color():
    RED   = "\033[1;31m"  
    BLUE  = "\033[1;34m"
    CYAN  = "\033[1;36m"
    GREEN = "\033[0;32m"
    RESET = "\033[0;0m"
    BOLD    = "\033[;1m"
    REVERSE = "\033[;7m"

class Obstacle:
    def __init__(self):
        self. x = 0
        self.y = 0
        self.radius = 0
        self.teta = 0
        self.alpha = 0
        self.collision_flag = 0
        self.past_collision_flag = 0
        self.total_radius = 0

class Boat:
    def __init__(self, radius=0):
        self.radius = radius
        self.ned_x = 0
        self.ned_y = 0
        self.yaw = 0
        self.u = 0
        self.v = 0
        self.vel = 0
        self.bearing = 0

class CollisionAvoidance:
    def __init__(self, exp_offset=0, safety_radius=0, u_max=0, u_min=0, 
        exp_gain=0, chi_psi=0, r_max=0, obstacle_mode=0):
        self.safety_radius = safety_radius
        self.u_max = u_max
        self.u_min = u_min
        self.chi_psi = chi_psi
        self.exp_gain = exp_gain
        self.exp_offset = exp_offset
        self.r_max = r_max
        self.obstacle_mode = obstacle_mode
        self.obs_list = []
        self.vel_list = []
        self.u_psi = 0
        self.u_r = 0
        self.boat = Boat()

        for i in range(0,21,1):
            obstacle = Obstacle()
            self.obs_list.append(obstacle)

    def avoid(self, ak, x1, y1, input_list, boat):
        '''
        @name: avoid
        @brief: If there is an impending collision, returns the velocity and 
            angle to avoid.
        @param: x1: x coordinate of the path starting-waypoint
                y1: y coordinate of the path starting-waypoint
                ak: angle from NED reference frame to path
                input_list: incomming obstacle list
                boat: boat class structure
        @return: bearing: bearing to avoid obstacles
                 velocity: velocity to avoid obstacles
        '''
        nearest_obs = []
        self.vel_list = []
        self.boat = boat

        vel_nedx,vel_nedy = self.body_to_ned(self.boat.u,self.boat.v,0,0)
        #print("self.u: " + str(self.boat.u))
        #print("self.boat.v: " + str(self.boat.v))
        #print("vel_nedx: " + str(vel_nedx))
        #print("vel_nedy " + str(vel_nedy))
        #print("ak: ", str(ak))
        vel_ppx,vel_ppy =  self.ned_to_pp(ak,0,0,vel_nedx,vel_nedy)
        #ppx,ppy = self.ned_to_pp(ak,x1,y1,self.boat.ned_x,self.boat.ned_y)

        self.check_obstacles(input_list)

        for i in range(0,len(self.obs_list),1):
            sys.stdout.write(Color.CYAN)
            print("obstacle"+str(i))
            sys.stdout.write(Color.RESET)
            print("obsx: " + str(self.obs_list[i].x))
            print("obsy: " + str(self.obs_list[i].y))
            print("obsradius: " + str(self.obs_list[i].radius))
        
            self.obs_list[i].total_radius = self.boat.radius + self.safety_radius + self.obs_list[i].radius
            collision, distance = self.get_collision(0, 0, vel_ppy, vel_ppx,i)
            #print("distance: " + str(distance)) 
            if collision:
                #u_obs = np.amin(u_obstacle)
                avoid_distance = self.calculate_avoid_distance(self.boat.u, self.boat.v, i)
                nearest_obs.append(avoid_distance - distance)
                #print("avoid_distance: " + str(avoid_distance)) 
                #print("distance: " + str(distance)) 
            else:
                nearest_obs.append(0)
                #self.vel_list.append(self.vel)
        
        if len(nearest_obs) > 0:
            print('nearest_obs max: ' + str(np.max(nearest_obs)))
            if np.max(nearest_obs)>0:
                index = nearest_obs.index(np.max(nearest_obs))
                if np.max(nearest_obs) > 0 and self.obs_list[index].alpha > 0:
                    self.boat.vel = np.min(self.vel_list)
                    sys.stdout.write(Color.BOLD)
                    print('index: ' + str(index))
                    sys.stdout.write(Color.RESET)
                    ppx,ppy = self.ned_to_pp(ak, x1, y1, self.boat.ned_x, self.boat.ned_y)
                    obs_ppx, obs_ppy = self.get_obstacle( ak, x1, y1, index)
                    self.dodge(vel_ppx, vel_ppy, ppx, ppy, obs_ppx, obs_ppy, index)
                else:
                    #rospy.loginfo("nearest_obs: " + str(nearest_obs[index])) 
                    sys.stdout.write(Color.BLUE)
                    print ('free')
                    sys.stdout.write(Color.RESET)
                #sys.stdout.write(Color.BOLD)
                #print("yaw: " + str(self.yaw))
                #print("bearing: " + str(self.bearing))
                #sys.stdout.write(Color.RESET)
        else:
            sys.stdout.write(Color.BLUE)
            print ('no obstacles')
            sys.stdout.write(Color.RESET)
        print('vel:' + str(self.boat.vel))
        
        return self.boat.bearing, self.boat.vel

    def check_obstacles(self, input_list):
        '''
        @name: check_obstacles
        @brief: Recieves incomming obstacles and checks if they must be merged.
        @param: input_list: incomming obstacle list
        @return: --
        '''
        sys.stdout.write(Color.RED)
        print("Check Obstacles:")
        sys.stdout.write(Color.RESET)
        for i in range(0,len(input_list),1):
            #self.obstacle = Obstacle()
            self.obs_list[i].x = input_list[i]['X']
            # Negative y to compensate Lidar reference frame
            self.obs_list[i].y = -input_list[i]['Y']
            self.obs_list[i].radius = input_list[i]['radius']
            print("self.obs_list[" + str(i)+ "].x: " + str(self.obs_list[i].x))
            print("self.obs_list[i].y: " + str(self.obs_list[i].y))
            print("self.obs_list[i].radius: " + str(self.obs_list[i].radius))
            print("self.obs_list[i].collision_flag: " + str(self.obs_list[i].collision_flag))
        i = 0
        j = 0 
        while i < (len(self.obs_list)-1):
            j = i + 1
            while j < len(self.obs_list):
                x = pow(self.obs_list[i].x-self.obs_list[j].x, 2)
                y = pow(self.obs_list[i].y-self.obs_list[j].y, 2)
                radius = self.obs_list[i].radius + self.obs_list[j].radius
                distance_centers = pow(x+y, 0.5)
                distance = distance_centers - radius
                #print("distance between i:" + str(i)+ " and j:" + str(j) + " = "+ str(distance))
                #print("boat distance: " + str((self.boat.radius + self.safety_radius)*2))
                if distance < 0:
                  j = j + 1
                elif distance <= (self.boat.radius + self.safety_radius)*2:
                    x,y,radius = self.merge_obstacles(i,j, distance_centers)
                    print("self.obs_list[i].y: " + str(self.obs_list[i].y))
                    print("self.obs_list[j].y: " + str(self.obs_list[j].y))
                    self.obs_list[i].x = x
                    self.obs_list[i].y = y
                    self.obs_list[i].radius = radius
                    print("self.obs_list[ij].y: " + str(self.obs_list[i].y))
                    print("self.obs_list[ij].radius: " + str(self.obs_list[i].radius))
                    self.obs_list[j].x = x
                    #print("self.obs_list[i].x: " + str(self.obs_list[j].x))
                    self.obs_list[j].y = y
                    self.obs_list[j].radius = radius
                    i = 0
                else:
                    j = j + 1

                sys.stdout.write(Color.RED)
                #print("Obstacle the same")
                sys.stdout.write(Color.RESET)
                #print("i: " + str(i))
                #print("j: " + str(j))
            i = i + 1
            #print("done j")
        #print(self.obs_list)
        return self.obs_list

    def merge_obstacles(self, i, j, distance_centers):
        '''
        @name: merge_obstacles
        @brief: Calculates new obstacle center and radius for merged obstacles.
        @param: i: first obstacle index
                j: second obstacle index
                distance_centers: distance of obstacles centers
        @return: x: merged obstacle center x
                 y: merged obstacle center y 
                 radius: merged obstacle radius
        '''
        # calculate centroid
        x = (self.obs_list[i].x + self.obs_list[j].x)/2
        y = (self.obs_list[i].y + self.obs_list[j].y)/2
        #calculte radius
        max_radius = max(self.obs_list[i].radius, self.obs_list[i+1].radius)
        radius = distance_centers/2 + max_radius
        sys.stdout.write(Color.RED)
        print("Merged obstacle:" + str(radius))
        sys.stdout.write(Color.RESET)
        return(x,y,radius)
    
    def get_collision(self, ppx, ppy, vel_ppy, vel_ppx, i):
        '''
        @name: get_collision
        @brief: Calculates if there is an impending collision with an obstacle.
        @param: ppx: boat parallel path position x
                ppy: boat parallel path position y
                vel_ppy: boat parallel path velocity y
                vel_ppx: boat parallel path velocity x
                i: obstacle index
        @return: collision: 1 = collision 0 = non-collision
                 distance: distance to obstacle
        '''
        collision = 0
        #print("Total Radius: " + str(total_radius))
        x_pow = pow(self.obs_list[i].x - ppx,2) 
        y_pow = pow(self.obs_list[i].y - ppy,2) 
        distance = pow((x_pow + y_pow),0.5)

        distance_free = distance - self.obs_list[i].total_radius
        print("Distance_free: " + str(distance_free))

        if distance < self.obs_list[i].total_radius:
            rospy.logwarn("CRASH")
        alpha_params = (self.obs_list[i].total_radius/distance)
        alpha = math.asin(alpha_params)
        beta = math.atan2(vel_ppy,vel_ppx)-math.atan2(self.obs_list[i].y-ppy,self.obs_list[i].x-ppx)
        if beta > math.pi: 
            beta = beta - 2*math.pi
        if beta < - math.pi: 
            beta = beta + 2*math.pi
        beta = abs(beta)
        if beta <= alpha or 1 == self.obs_list[i].collision_flag:
            #print('beta: ' + str(beta))
            #print('alpha: ' + str(alpha))
            print("COLLISION")
            collision = 1
            self.obs_list[i].collision_flag = 1
            self.calculate_avoid_angle(ppy, distance, ppx, i)
            #self.get_velocity(distance_free, i)
        else:
            #self.obs_list[i].collision_flag = 0
            self.obs_list[i].tetha = 0
        self.get_velocity(distance_free, i)
        return collision, distance

    def calculate_avoid_angle(self, ppy, distance, ppx, i):
        '''
        @name: calculate_avoid_angle
        @brief: Calculates angle needed to avoid obstacle
        @param: ppy: boat y coordiante in path reference frame 
                distance: distance from center of boat to center of obstacle 
                ppx: boat x coordiante in path reference frame 
                i: osbtacle index
        @return: --
        '''
        #print("ppx: " + str(ppx) + " obs: " + str(self.obs_list[i].x))
        #print("ppy: " + str(ppy) + " obs: " + str(self.obs_list[i].y))
        self.obs_list[i].total_radius = self.obs_list[i].total_radius + .30
        tangent_param = abs((distance - self.obs_list[i].total_radius) * (distance + self.obs_list[i].total_radius))
        #print("distance: " + str(distance))
        tangent = pow(tangent_param, 0.5)
        #print("tangent: " + str(tangent))
        teta = math.atan2(self.obs_list[i].total_radius,tangent)
        #print("teta: " + str(teta))
        gamma1 = math.asin(abs(ppy-self.obs_list[i].y)/distance)
        #print("gamma1: " + str(gamma1))
        gamma = ((math.pi/2) - teta) + gamma1
        #print("gamma: " + str(gamma))
        self.obs_list[i].alpha = (math.pi/2) - gamma
        print("alpha: " + str(self.obs_list[i].alpha))
        hb = abs(ppy-self.obs_list[i].y)/math.cos(self.obs_list[i].alpha)
        #print("hb: " + str(hb))
        b = self.obs_list[i].total_radius - hb
        #print("i: " + str(i))
        print("b: " + str(b))
        self.obs_list[i].teta = math.atan2(b,tangent)
        print("teta: " + str(self.obs_list[i].teta))
        if self.obs_list[i].alpha < 0.0:
            self.obs_list[i].collision_flag = 0
            sys.stdout.write(Color.BOLD)
            print("Collision flag off")
            sys.stdout.write(Color.RESET)

    def get_velocity(self, distance_free, i):
        '''
        @name: get_velocity
        @brief: Calculates velocity needed to avoid obstacle
        @param: distance_free: distance to collision  
                i: osbtacle index
        @return: --
        '''
        u_r_obs = 1/(1 + math.exp(-self.exp_gain*(distance_free*(1/5) - self.exp_offset)))
        u_psi_obs = 1/(1 + math.exp(self.exp_gain*(abs(self.obs_list[i].teta)*self.chi_psi -self.exp_offset)))
        #print("u_r_obs: " + str( u_r_obs))
        #print("u_psi_obs" + str(u_psi_obs))
        #print("Vel chosen: " + str(np.min([self.u_psi, self.u_r, u_r_obs, u_psi_obs])))
        self.vel_list.append((self.u_max - self.u_min)*np.min([self.u_psi, self.u_r, u_r_obs, u_psi_obs]) + self.u_min)

    def calculate_avoid_distance(self, vel_ppx, vel_ppy, i):
        '''
        @name: calculate_avoid_distance
        @brief: Calculates distance at wich it is necesary to leave path to 
            avoid obstacle
        @param: vel_ppx: boat velocity x  in path reference frame 
                vel_ppy: boat velocity y  in path reference frame 
                i: obstacle index
        @return: avoid_distance: returns distance at wich it is necesary to 
            leave path to avoid obstacle
        '''
        time = (self.obs_list[i].teta/self.r_max) + 3
        #print("time: " + str(time))
        eucledian_vel = pow((pow(vel_ppx,2) + pow(vel_ppy,2)),0.5)
        #print("vel: " + str(eucledian_vel))
        #print("self.boat.vel: " + str(self.boat.vel))
        #avoid_distance = time * eucledian_vel + total_radius +.3
        avoid_distance = time * self.boat.vel + self.obs_list[i].total_radius +.3 #+.5
        return (avoid_distance)

    def get_obstacle(self, ak, x1, y1, i):
        '''
        @name: get_obstacle
        @brief: Gets obstacle coodinates in parallel path reference frame
        @param: ak: coordinate frame angle difference
                x1: starting x coordinate
                y1: starting y coordinate
                i: osbtacle index
        @return: obs_ppx: obstalce x in parallel path reference frame
                 obs_ppy: obstalce y in parallel path reference frame
        '''
        # NED obstacles
        if (self.obstacle_mode == 0):
            obs_ppx,obs_ppy = self.ned_to_pp(ak,x1,y1,self.obs_list[i].x,self.obs_list[i].y)
        # Body obstacles
        if (self.obstacle_mode == 1):
            obs_nedx, obs_nedy = self.body_to_ned(self.obs_list[i].x, self.obs_list[i].y, self.boat.ned_x, self.boat.ned_y)
            obs_ppx,obs_ppy = self.ned_to_pp(ak, x1, y1, obs_nedx, obs_nedy)
        return(obs_ppx, obs_ppy)

    def dodge(self, vel_ppx, vel_ppy , ppx, ppy, obs_ppx, obs_ppy, i):
        '''
        @name: dodge
        @brief: Calculates angle needed to avoid obstacle
        @param: vel_ppx: boat velocity x  in path reference frame 
                vel_ppy: boat velocity y  in path reference frame 
                ppx: boat x coordiante in path reference frame 
                ppy: boat y coordiante in path reference frame 
                obs_ppx: osbtacle x coordiante in path reference frame
                obs_ppy: osbtacle y coordiante in path reference frame
                i: obstacle index
        @return: --
        '''
        eucledian_vel = pow((pow(vel_ppx,2) + pow(vel_ppy,2)),0.5)
        # Euclaedian vel must be different to cero to avoid math error
        if eucledian_vel != 0:
            #print("vel x: " + str(vel_ppx))
            #print("vel y: " + str(vel_ppy))
            #print("obs_y: " + str(obs_y))
            # obstacle in center, this is to avoid shaky behaivor
            if abs(self.obs_list[i].y) < 0.1:
                angle_difference = self.boat.bearing - self.boat.yaw
                #print("angle diference: " + str(angle_difference))
                if 0.1 > abs(angle_difference) or 0 > (angle_difference):
                    self.boat.bearing = self.boat.yaw - self.obs_list[i].teta
                    sys.stdout.write(Color.RED)
                    print("center left -")
                    sys.stdout.write(Color.RESET)
                else:
                    self.boat.bearing = self.boat.yaw + self.obs_list[i].teta
                    sys.stdout.write(Color.GREEN)
                    print("center right +")
                    sys.stdout.write(Color.RESET)
            else:
                eucledian_pos = pow((pow(obs_ppx - ppx,2) + pow(obs_ppy - ppy,2)),0.5)
                #print("eucledian_vel " + str(eucledian_vel))
                #print("eucladian_pos: " + str(eucledian_pos))
                unit_vely = vel_ppy/eucledian_vel 
                unit_posy = (obs_ppy - ppy)/eucledian_pos
                #print("unit_vely " + str(unit_vely))
                #print("unit_posy: " + str(unit_posy))
                if unit_vely <= unit_posy:
                    self.boat.bearing = self.boat.yaw - self.obs_list[i].teta
                    sys.stdout.write(Color.RED)
                    print("left -")
                    sys.stdout.write(Color.RESET)
                    '''
                    if (abs(self.avoid_angle) > (math.pi/2)):
                        self.avoid_angle = -math.pi/2
                    '''
                else:
                    self.boat.bearing = self.boat.yaw + self.obs_list[i].teta
                    sys.stdout.write(Color.GREEN)
                    print("right +")
                    sys.stdout.write(Color.RESET)
                    '''
                    if (abs(self.avoid_angle) > (math.pi/3)):
                        self.avoid_angle = math.pi/2
                    '''
                '''
                if unit_vely <= unit_posy:
                    self.teta = -self.teta
                    
                else:
                    self.teta =  self.teta
                    
                '''

    def body_to_ned(self, x2, y2, offsetx, offsety):
        '''
        @name: body_to_ned
        @brief: Coordinate transformation between body and NED reference frames.
        @param: x2: target x coordinate in body reference frame
                y2: target y coordinate in body reference frame
                offsetx: offset x in ned reference frame
                offsety: offset y in ned reference frame
        @return: ned_x2: target x coordinate in ned reference frame
                 ned_y2: target y coordinate in ned reference frame
        '''
        p = np.array([x2, y2])
        J = np.array([[math.cos(self.boat.yaw), -1*math.sin(self.boat.yaw)],
                      [math.sin(self.boat.yaw), math.cos(self.boat.yaw)]])
        n = J.dot(p)
        ned_x2 = n[0] + offsetx
        ned_y2 = n[1] + offsety
        return (ned_x2, ned_y2)

    def ned_to_pp(self, ak, ned_x1, ned_y1, ned_x2, ned_y2):
        '''
        @name: ned_to_ned
        @brief: Coordinate transformation between NED and body reference frames.
        @param: ak: angle difference from ned to parallel path 
                ned_x1: origin of parallel path x coordinate in ned reference 
                    frame
                ned_y1: origin of parallel path y coordinate in ned reference 
                    frame
                ned_x2: target x coordinate in ned reference frame
                ned_y2: target y coordinate in ned reference frame
        @return: pp_x2: target x coordinate in parallel path reference frame
                 pp_y2: target y coordinate in parallel path reference frame
        '''
        n = np.array([ned_x2 - ned_x1, ned_y2 - ned_y1])
        J = np.array([[math.cos(ak), -1*math.sin(ak)],
                      [math.sin(ak), math.cos(ak)]])
        J = np.linalg.inv(J)
        pp = J.dot(n)
        pp_x2 = pp[0]
        pp_y2 = pp[1]
        return (pp_x2, pp_y2)
