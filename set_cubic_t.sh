cd cubic
make 
sudo rmmod tcp_cubic_t
sudo insmod tcp_cubic_t.ko
# sudo sysctl -w net.ipv4.tcp_congestion_control=cubic_t
sudo dmesg -C
cd ..
