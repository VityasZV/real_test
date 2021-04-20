cd vityas 
make 
sudo rmmod tcp_vityas
# _PACKET_LIMIT _PROBABILITY env variables
sudo insmod tcp_vityas.ko probability=77  packet_limit=60
sudo sysctl -w net.ipv4.tcp_congestion_control=vityas
sudo dmesg -C
cd ..
