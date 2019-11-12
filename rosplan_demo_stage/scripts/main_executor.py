#!/usr/bin/env python
import rospkg
import rospy
import sys
import time
import os

from std_srvs.srv import Empty, EmptyResponse
from rosplan_knowledge_msgs.srv import SetInt, GetAttributeService
from rosplan_interface_mapping.srv import CreatePRM
from rosplan_dispatch_msgs.srv import DispatchService, DispatchServiceResponse

# get path of pkg
rospack = rospkg.RosPack()
rospy.init_node("coordinator")

# load parameters
wait_for_rviz = rospy.get_param('~wait_for_rviz', False)
max_sample_size = rospy.get_param('~max_sample_size', 10)
max_prm_size = rospy.get_param('~max_prm_size', 1000)
approach = rospy.get_param('~approach', 0)

# wait for services
rospy.wait_for_service('/rosplan_roadmap_server/create_prm')
rospy.wait_for_service('/rosplan_problem_interface/problem_generation_server')
rospy.wait_for_service('/rosplan_planner_interface/planning_server')
rospy.wait_for_service('/rosplan_knowledge_base/state/propositions')
if approach == 0:
    rospy.wait_for_service('/waypoint_sampler/sample_waypoints')

# begin experiment
try:

    # generate dense PRM
    rospy.loginfo("KCL: (%s) Creating PRM of size %i" % (rospy.get_name(), max_prm_size))
    prm = rospy.ServiceProxy('/rosplan_roadmap_server/create_prm', CreatePRM)        
    if not prm(max_prm_size,0.8,1.6,2.0,50,200000):
        rospy.logerr("KCL: (%s) No PRM was made" % rospy.get_name())

    ### SAMPLING APPROACH ###
    if approach == 0:
        sample_count = 1
        goal_achieved = False
        while sample_count < max_sample_size:

            rospy.loginfo("KCL: (%s) Sampling %i waypoints" % (rospy.get_name(), sample_count))
            smp = rospy.ServiceProxy('/waypoint_sampler/sample_waypoints', SetInt)        
            if not smp(sample_count):
                rospy.logerr("KCL: (%s) No sample was made" % rospy.get_name())

            # wait for the sensing interface to catch up
            rospy.loginfo("KCL: (%s) Waiting for visibility to be added to KB" % rospy.get_name())
            propcount = 0
            while propcount < 1:
                vis = rospy.ServiceProxy('/rosplan_knowledge_base/state/propositions', GetAttributeService)
                vis_response = vis("doughnut_visible_from")
                if not vis_response:
                    rospy.logerr("KCL: (%s) Failed to call the KB" % rospy.get_name())
                    quit()
                propcount = len(vis_response.attributes)
                rospy.sleep(0.5)

            rospy.loginfo("KCL: (%s) Calling problem generation" % rospy.get_name())
            pg = rospy.ServiceProxy('/rosplan_problem_interface/problem_generation_server', Empty)
            if not pg():
                rospy.logerr("KCL: (%s) No problem was generated!" % rospy.get_name())

            rospy.loginfo("KCL: (%s) Calling planner" % rospy.get_name())
            pi = rospy.ServiceProxy('/rosplan_planner_interface/planning_server', Empty)
            if not pi():
                rospy.logerr("KCL: (%s) No plan could be found. Ending the loop." % rospy.get_name())
                break

            sample_count += 1

except rospy.ServiceException, e:
    rospy.logerr("KCL: (%s) Service call failed: %s" % (rospy.get_name(), e))
