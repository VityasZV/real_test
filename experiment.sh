#!/bin/bash
set +x

if [ "$(whoami)" != "root" ]; then
	echo "Write <sudo> please"
 	exit 1
fi

pip3 install --force-reinstall scipy 

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
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} root handle 1: tbf rate 10mbit burst 1536b latency 1ms
ip netns exec ${array_host[1]} tc qdisc add dev ${array_eth[1]} parent 1:1 handle 10: netem delay 20ms
# разобраться с командой сверху


echo "CHECK THAT EVERYTHING setted ok"
echo "server ifconfig: "
ip netns exec ${array_host[0]} ifconfig

echo "client ifconfig: "
ip netns exec ${array_host[1]} ifconfig
echo "IFCONFIG CHECKED Successfully"


step_array=(0 1)
forecast_method_array=(0 1 2 3)
packet_limit_array=(25)
# probability_array=(40 60 70 80 90)
probability_array=(60 70 80 90)
experiments_array=(125)
#experiment part
rm -rf test_output
mkdir test_output
for s in 0
do
for k in 0 1 2 3
do
for i in 0
do
for j in 2
for e in {1..1}
do 
	. clear_vityas.sh
	cd vityas 
	make
	rmmod tcp_vityas
	# _PACKET_LIMIT _PROBABILITY _FORECAST env variables
	export _PACKET_LIMIT=${packet_limit_array[$i]}
	export _PROBABILITY=${probability_array[$j]}
	export _FORECAST=${forecast_method_array[$k]}
	export _STEP=${step_array[$s]}

	insmod tcp_vityas.ko probability=$_PROBABILITY packet_limit=$_PACKET_LIMIT forecast_method=$_FORECAST step=$_STEP
	cd ..
	experiment_name=test_f_$_FORECAST\_p_$_PROBABILITY\_l_$_PACKET_LIMIT\_e_$e
	dir_name=test_output/$experiment_name
	mkdir $dir_name
	start_time=$(date +"%T")

	echo "VITYAS Experiment start (P=$_PROBABILITY; L=$_PACKET_LIMIT; F=$_FORECAST; S=$_STEP):"

	ip netns exec ${array_host[0]} iperf3 -s -p 5201 -f K  &
	export iperf_serv=$!
	ip netns exec ${array_host[1]} iperf3 -c 192.168.1.1 -B 192.168.1.2 -p 5201 -f K -t 40 -C vityas > $dir_name/$experiment_name\_iperf.txt &
	export iperf_client=$!
	EXPERIMENT="vityas_$i" python3 weibull_threads_iperf.py &
	export weibull=$!
	echo "waiting 60 seconds for iperf client to generate some traffic"
	wait $iperf_client
	echo "waiting weibull_threads"
	wait $weibull
	echo "killing iperf server"
	kill $iperf_serv

	echo "Saving dmesg of vityas alg start time: $start_time"
	journalctl -k --since $start_time > $dir_name/$experiment_name\_dmesg.txt
	echo "VITYAS Experiment end."
done
done
done
done
. clear_vityas.sh

traditional=("cubic_t" "bbr_t")

for k in 0 1
do
t=${traditional[$k]}
echo "$t Experiment start:"

. set_$t.sh

mkdir test_output/$t
start_time=$(date +"%T")
ip netns exec ${array_host[0]} iperf3 -s -p 5201 -f K  &
export iperf_serv=$!
EXPERIMENT="$t" python3 weibull_threads_iperf.py &
export weibull=$!
ip netns exec ${array_host[1]} iperf3 -c 192.168.1.1 -B 192.168.1.2 -p 5201 -f K -t 40 -C $t > test_output/$t/$t\_iperf.txt &
export iperf_client=$!

echo "waiting 60 seconds for iperf client to generate some traffic"
wait $iperf_client
echo "wait weibull"
wait $weibull
echo "killing iperf server"
kill $iperf_serv

echo "saving dmesg output of cubic"
journalctl -k --since $start_time > test_output/$t/$t\_dmesg.txt
echo "$t Experiment end."
. clear_$t.sh
done


echo "finito la comedia, now Running Python script for saving csv_files of iperf and dmesg of each experiment..."

python3 save_exp_to_csv_file.py
python3 draw_graphs.py
