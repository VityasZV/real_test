#!/bin/bash
set +x

if [ "$(whoami)" != "root" ]; then
	echo "Write <sudo> please"
 	exit 1
fi
array_eth=(eth1 eth2)
array_host=(ns_server ns_client)
echo "delete all previos topology"
. clear_vityas.sh
. clear_cubic.sh
for i in 0 1
do
	ip netns exec ${array_host[$i]} ip link set dev ${array_eth[$i]} netns 1
	ip netns del ${array_host[$i]}
done

for i in 0 1
do
	ifconfig ${array_eth[$i]} down
	ip link del ${array_eth[$i]}
done

. clear_vityas.sh
. clear_cubic.sh

echo "create experimental stand"

for i in 0
do 
	let j=$i+1
	ip link add ${array_eth[$i]} type veth peer name ${array_eth[$j]}
done

echo "check interfaces"

ip link list
ifconfig

echo "create hostd and virtual interfaces for them"
for i in 0 1
do
	ip netns add ${array_host[$i]}
done

for i in 0 1
do
	let j=$i+1
	ip link set ${array_eth[$i]} netns ${array_host[$i]}
    ip netns exec ${array_host[$i]} ip addr add dev ${array_eth[$i]} 192.168.1.${j}/24
    ip netns exec ${array_host[$i]} ip link set dev ${array_eth[$i]} up
done

for i in 0 1
do 
	ip netns exec ${array_host[$i]} ifconfig ${array_eth[$i]} up
done


echo "setting tc params..."
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} root handle 1: tbf rate 100mbit burst 1536b latency 10ms
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} parent 1:1 handle 10: netem delay 20ms
# разобраться с командой сверху


echo "CHECK THAT EVERYTHING setted ok"
echo "server ifconfig: "
ip netns exec ${array_host[0]} ifconfig

echo "client ifconfig: "
ip netns exec ${array_host[1]} ifconfig
echo "IFCONFIG CHECKED Successfully"

# ip netns exec ns_client ping 192.168.1.1 -n 10 &
# echo "waiting for ping"
# wait $!

# echo "ping finished"




packet_limit_array=(65 50 100)
probability_array=(77 90 60)
#experiment part
rm -rf test_output
mkdir test_output
for i in 0
do 
	. clear_vityas.sh
	cd vityas 
	make 
	rmmod tcp_vityas
	# _PACKET_LIMIT _PROBABILITY env variables
	export _PACKET_LIMIT=${packet_limit_array[$i]}
	export _PROBABILITY=${probability_array[$i]}

	insmod tcp_vityas.ko probability=$_PROBABILITY  packet_limit=$_PACKET_LIMIT
	# sysctl -w net.ipv4.tcp_congestion_control=vityas
	dmesg -C
	cd ..
	mkdir test_output/test_p_$_PROBABILITY\_l_$_PACKET_LIMIT


	echo "VITYAS Experiment start (P=$_PROBABILITY; L=$_PACKET_LIMIT):"
	ip netns exec ${array_host[0]} iperf3 -s -f K  &
	export iperf_serv=$!
	ip netns exec ${array_host[1]} iperf3 -c 192.168.1.1 -B 192.168.1.2 -f K -t 14 -C vityas > test_output/test_p_$_PROBABILITY\_l_$_PACKET_LIMIT/experiment_test_p_$_PROBABILITY\_l_$_PACKET_LIMIT\_iperf.txt &
	export iperf_client=$!

	echo "waiting 30 seconds for iperf client to generate some traffic"
	wait $iperf_client
	echo "killing iperf server"
	kill $iperf_serv

	echo "Saving dmesg of vityas alg"
	ip netns exec ns_client dmesg > test_output/test_p_$_PROBABILITY\_l_$_PACKET_LIMIT/experiment_test_p_$_PROBABILITY\_l_$_PACKET_LIMIT\_dmesg.txt
	dmesg -C
	echo "VITYAS Experiment end."
done 

echo "CUBIC Experiment start:"

. clear_vityas.sh
. set_cubic.sh

mkdir test_output/cubic
ip netns exec ${array_host[0]} iperf3 -s -f K  &
export iperf_serv=$!
ip netns exec ${array_host[1]} iperf3 -c 192.168.1.1 -B 192.168.1.2 -f K -t 14 -C cubic_t > test_output/cubic/experiment_cubic_iperf.txt &
export iperf_client=$!

echo "waiting 30 seconds for iperf client to generate some traffic"
wait $iperf_client
echo "killing iperf server"
kill $iperf_serv

echo "saving dmesg output of cubic"
ip netns exec ns_client dmesg > test_output/cubic/experiment_cubic_dmesg.txt
dmesg -C
echo "CUBIC Experiment end."
. clear_cubic.sh


echo "finito la comedia, now Running Python script for saving csv_files of iperf and dmesg of each experiment..."

python3 save_exp_to_csv_file.py
