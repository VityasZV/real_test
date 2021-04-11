cd vityas 
make 
sudo rmmod tcp_vityas
sudo insmod tcp_vityas.ko
sudo sysctl -w net.ipv4.tcp_congestion_control=vityas
sudo dmesg -C
cd ..
