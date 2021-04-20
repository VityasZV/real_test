#!/bin/bash


if [ "$(whoami)" != "root" ]; then
	echo "Write <sudo> please"
 	exit 1
fi
array_eth=(eth1, eth2)
array_host=(ns_server, ns_client)
#delete all previos topology
for i in 0 1
do
	ip netns exec ${array_host[$i]} ip link set dev ${array_veth[$i*2 + 5]} netns 1
	ip netns del ${array_host[$i]}
done

for i in 0 1
do
	ifconfig ${array_veth[$i]} down
	ip link del ${array_veth[$i]}
done

#create experimental stand 
for i in 0 1
do 
	ip link add ${array_eth[$i]} type veth peer name ${array_veth[$i]}
    ifconfig ${array_eth[$i]} up
done

#create hostd and virtual interfaces for them
for i in 0 1
do
	ip netns add ${array_host[$i]}
	ip link set ${array_eth[$i]} netns ${array_host[$i]}
    ip netns exec ${array_host[$i]} ip ${array_eth[$i]} add dev ${array_eth[$i]} 10.0.0.${i+1}/24
    ip netns exec ${array_host[$i]} ip link set dev ${array_eth[$i]} up
done

#experiment part

. clear_vityas.sh
cd vityas 
make 
rmmod tcp_vityas
# _PACKET_LIMIT _PROBABILITY env variables
export _PACKET_LIMIT=65
export _PROBABILITY=77

sudo insmod tcp_vityas.ko probability=_PROBABILITY  packet_limit=_PACKET_LIMIT
sudo sysctl -w net.ipv4.tcp_congestion_control=vityas
sudo dmesg -C
cd ..

echo "setting tc params..."
	
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} root netem delay 200ms
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} root tbf rate 1mbit burst 32kbit latency 400ms


ip netns exec ${array_host[0]} iperf3 -s -f K  &
export iperf_serv= $!
ip netns exec ${array_host[0]} iperf3 -c 10.0.0.0 -f K -t 30 &
export iperf_client = $!

echo "waiting 30 seconds for iperf client to generate some traffic"
wait iperf_client
echo "killing iperf server"
kill iperf_serv

echo "finito la comedia mothafuckuz, look at the dmesg output in file experimant_result.txt"

dmesg > experiment_result.txt
