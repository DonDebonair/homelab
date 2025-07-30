#!/bin/bash

while ! ip link show eth0 | grep -q 'state UP'; do
    sleep 1
done

param_vlan_name="macvlan-shim"
param_interface="eth0"
ip_range="192.168.1.192/27"
host_ip="192.168.1.223"


echo "Creating interface to bridge host and docker network"

status=''

# (re-)create macvlan bridge attached to the network interface
status=$(ip link | grep "${param_vlan_name}")
if [ ! -z "$status" ] ; then
    echo "Removing existing link '${param_vlan_name}'"
    ip link set "${param_vlan_name}" down > /dev/null 2>&1
    ip link delete "${param_vlan_name}" > /dev/null 2>&1
fi
echo "Adding macvlan interface '${param_vlan_name}' "
ip link add "${param_vlan_name}" link "${param_interface}" type macvlan mode bridge

# assign host address to macvlan
status=$(ip addr | grep "${param_vlan_name}")
if [ -z "${status}" ] ; then
    echo "Assign IP address '${host_ip}' to '${param_vlan_name}'"
    ip addr add "${host_ip}/32" dev "${param_vlan_name}" > /dev/null 2>&1
else # this should never happen because link is deleted above if exists
    echo "Updating current IP address of '${param_vlan_name}' to '${host_ip}'"
    ip addr change "${host_ip}/32" dev "${param_vlan_name}" > /dev/null 2>&1
fi

# bring macvlan interface up
echo "Bringing up interface '${param_vlan_name}'"
ip link set "${param_vlan_name}" up > /dev/null 2>&1

# add route to Pi-hole IP on macvlan interface
status=$(ip route | grep "${param_vlan_name}" | grep "${ip_range}")
if [ -z "${status}" ] ; then
    echo "Adding static route from '${ip_range}' to '${param_vlan_name}'"
    ip route add "${ip_range}" dev "${param_vlan_name}" > /dev/null 2>&1
fi

# check virtual adapter status
status=$(ip route | grep "${param_vlan_name}")
if [ -z "${status}" ] ; then
    echo "Could not create macvlan interface"
fi
