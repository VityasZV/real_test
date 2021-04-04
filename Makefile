obj-m += tcp_vityas.o
all:
		make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
clean:
		make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
install:
		make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
		sudo cp tcp_vityas.ko /lib/modules/5.8.0-44-generic/kernel/net/ipv4/
test:
	# We put a — in front of the rmmod command to tell make to ignore
	# an error in case the module isn’t loaded.
	-sudo rmmod tcp_vityas
	# Clear the kernel log without echo
	sudo dmesg -C
	# Insert the module
	sudo insmod tcp_vityas.ko

	# Display the kernel log
	dmesg
