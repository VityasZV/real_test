// SPDX-License-Identifier: GPL-2.0-only
/*
 * TCP CUBIC: Binary Increase Congestion control for TCP v2.3
 * Home page:
 *      http://netsrv.csc.ncsu.edu/twiki/bin/view/Main/BIC
 * This is from the implementation of CUBIC TCP in
 * Sangtae Ha, Injong Rhee and Lisong Xu,
 *  "CUBIC: A New TCP-Friendly High-Speed TCP Variant"
 *  in ACM SIGOPS Operating System Review, July 2008.
 * Available from:
 *  http://netsrv.csc.ncsu.edu/export/cubic_a_new_tcp_2008.pdf
 *
 * CUBIC integrates a new slow start algorithm, called HyStart.
 * The details of HyStart are presented in
 *  Sangtae Ha and Injong Rhee,
 *  "Taming the Elephants: New TCP Slow Start", NCSU TechReport 2008.
 * Available from:
 *  http://netsrv.csc.ncsu.edu/export/hystart_techreport_2008.pdf
 *
 * All testing results are available from:
 * http://netsrv.csc.ncsu.edu/wiki/index.php/TCP_Testing
 *
 * Unless CUBIC is enabled and congestion window is large
 * this behaves the same as the original Reno.
 */

#include <linux/mm.h>
#include <linux/module.h>
#include <linux/math64.h>
#include <net/tcp.h>

#define BICTCP_BETA_SCALE    1024	/* Scale factor beta calculation
					 * max_cwnd = snd_cwnd * beta
					 */
#define	BICTCP_HZ		10	/* BIC HZ 2^10 = 1024 */

/* Two methods of hybrid slow start */
#define HYSTART_ACK_TRAIN	0x1
#define HYSTART_DELAY		0x2

/* Number of delay samples for detecting the increase of delay */
#define HYSTART_MIN_SAMPLES	8
#define HYSTART_DELAY_MIN	(4000U)	/* 4 ms */
#define HYSTART_DELAY_MAX	(16000U)	/* 16 ms */
#define HYSTART_DELAY_THRESH(x)	clamp(x, HYSTART_DELAY_MIN, HYSTART_DELAY_MAX)

#define buffs_size 600
#define ack_buff_size 600

static int fast_convergence __read_mostly = 1;
static int beta __read_mostly = 717;	/* = 717/1024 (BICTCP_BETA_SCALE) */
static int initial_ssthresh __read_mostly;
static int bic_scale __read_mostly = 41;
static int tcp_friendliness __read_mostly = 1;

static int hystart __read_mostly = 1;
static int hystart_detect __read_mostly = HYSTART_ACK_TRAIN | HYSTART_DELAY;
static int hystart_low_window __read_mostly = 16;
static int hystart_ack_delta_us __read_mostly = 2000;

static u64 buffer_speed[buffs_size]; //saving last 3 speeds
static u64 new_estimated_speed;
static u64 last_mistakes[buffs_size];
static u64 new_acked = 0U;
static int count = 0; //count until 10 before calculating speed
// static u64 all_acked = 0U;
static u64 acked_buffer[ack_buff_size];
static u32 acked_time[ack_buff_size];

static bool estim_round_started = false;
static int inserted_values = 0;
static short int probability = 60;
static u64 z_index;
static u64 rms;
static short int packet_limit = 50;
static short int forecast_method = 0; //0 for moving average, 1 for moving average with weights, 2 for trend aga 
static short int step = 0; //0 for down 1 for up
static u32 cube_rtt_scale __read_mostly;
static u32 beta_scale __read_mostly;
static u64 cube_factor __read_mostly;

/* Note parameters that are used for precomputing scale factors are read-only */
module_param(fast_convergence, int, 0644);
MODULE_PARM_DESC(fast_convergence, "turn on/off fast convergence");
module_param(beta, int, 0644);
MODULE_PARM_DESC(beta, "beta for multiplicative increase");
module_param(initial_ssthresh, int, 0644);
MODULE_PARM_DESC(initial_ssthresh, "initial value of slow start threshold");
module_param(bic_scale, int, 0444);
MODULE_PARM_DESC(bic_scale, "scale (scaled by 1024) value for bic function (bic_scale/1024)");
module_param(tcp_friendliness, int, 0644);
MODULE_PARM_DESC(tcp_friendliness, "turn on/off tcp friendliness");
module_param(hystart, int, 0644);
MODULE_PARM_DESC(hystart, "turn on/off hybrid slow start algorithm");
module_param(hystart_detect, int, 0644);
MODULE_PARM_DESC(hystart_detect, "hybrid slow start detection mechanisms"
		 " 1: packet-train 2: delay 3: both packet-train and delay");
module_param(hystart_low_window, int, 0644);
MODULE_PARM_DESC(hystart_low_window, "lower bound cwnd for hybrid slow start");
module_param(hystart_ack_delta_us, int, 0644);
MODULE_PARM_DESC(hystart_ack_delta_us, "spacing between ack's indicating train (usecs)");

module_param(probability, short, 0);
MODULE_PARM_DESC(probability, "A short integer for describing probability");
module_param(packet_limit, short, 0);
MODULE_PARM_DESC(packet_limit, "limit for renewing average speed value");
module_param(forecast_method, short, 0);
MODULE_PARM_DESC(forecast_method, "strategy for point forecast of speed");
module_param(step, short, 0);
MODULE_PARM_DESC(step, "strategy for stepping from point forecast (up or down)");


/* BIC TCP Parameters */
struct bictcp {
	u32	cnt;		/* increase cwnd by 1 after ACKs */
	u32	last_max_cwnd;	/* last maximum snd_cwnd */
	u32	last_cwnd;	/* the last snd_cwnd */
	u32	last_time;	/* time when updated last_cwnd */
	u32	bic_origin_point;/* origin point of bic function */
	u32	bic_K;		/* time to origin point
				   from the beginning of the current epoch */
	u32	delay_min;	/* min delay (usec) */
	u32	epoch_start;	/* beginning of an epoch */
	u32	ack_cnt;	/* number of acks */
	u32	tcp_cwnd;	/* estimated tcp cwnd */
	u16	unused;
	u8	sample_cnt;	/* number of samples to decide curr_rtt */
	u8	found;		/* the exit point is found? */
	u32	round_start;	/* beginning of each round */
	u32	end_seq;	/* end_seq of the round */
	u32	last_ack;	/* last time when the ACK spacing is close */
	u32	curr_rtt;	/* the minimum rtt of current round */
};

// u64 int_sqrt(u64 x)
// {
// 	u64 op, res, one;
// 	op = x;
// 	res = 0;
// 	one = 1U << (BITS_PER_LONG - 2);
// 	while (one > op)
// 		one >>= 2;
// 	while (one != 0) {
// 		if (op >= res + one) {
// 			op = op - (res + one);
// 			res = res +  2 * one;
// 		}
// 		res /= 2;
// 		one /= 4;
// 	}
// 	return res;
// }

void root_mean_square_deviation(void) {
	int i = 0;
	rms = 0;
	while (i < buffs_size) {
		rms+=last_mistakes[i]*last_mistakes[i];
		++i;
	}
	if (inserted_values != 0) {
		rms/=inserted_values;
	}
	else {
		return;
	}
	u64 sqr;
	sqr = int_sqrt(rms);
	rms = sqr;
}


static inline void bictcp_reset(struct bictcp *ca)
{
	memset(ca, 0, offsetof(struct bictcp, unused));
	ca->found = 0;
}

static inline u32 bictcp_clock_us(const struct sock *sk)
{
	return tcp_sk(sk)->tcp_mstamp;
}

static inline void bictcp_hystart_reset(struct sock *sk)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct bictcp *ca = inet_csk_ca(sk);

	ca->round_start = ca->last_ack = bictcp_clock_us(sk);
	ca->end_seq = tp->snd_nxt;
	ca->curr_rtt = ~0U;
	ca->sample_cnt = 0;
}

static void bictcp_init(struct sock *sk)
{
	printk(KERN_INFO "Vityas test BIT_TCP_INIT");
	struct bictcp *ca = inet_csk_ca(sk);

	bictcp_reset(ca);

	if (hystart)
		bictcp_hystart_reset(sk);

	if (!hystart && initial_ssthresh)
		tcp_sk(sk)->snd_ssthresh = initial_ssthresh;
}

void go_to_zero(void) {
	int i = 0;
	new_acked = 0U;
	// inserted_values = 0;
	new_estimated_speed = 0U;
	// while (i < buffs_size) {
	// 	buffer_speed[i] = 0U;
	// 	last_mistakes[i] = 0U;
	// 	++i;
	// }
	i = 0;
	// while (i < ack_buff_size) {
	// 	acked_buffer[i] = 0U;
	// 	acked_time[i] = 0U;
	// 	++i;	
	// }
}

u64 get_tt(void) {
	return (acked_time[ack_buff_size-1] - acked_time[0]) * 10/ HZ;
}

u64 speed_forecast_moving_average(struct bictcp *ca) {
	u64 estimated_speed = 0;
	int i = 0;
	while (i < buffs_size) {
		estimated_speed += buffer_speed[i];
		++i;
	}
	if (inserted_values == 0) {
		printk("WTF INSERTED VALUES IS 0 if it should be at least 1");
	}
	else {
		estimated_speed = estimated_speed / inserted_values;
	}
	u64 tt = get_tt();
	printk(KERN_INFO "forecast CWND=?; SPEED=%llu", estimated_speed*tt*1000/ca->curr_rtt);
	return estimated_speed;
}

u64 speed_forecast_moving_average_weighted(struct bictcp *ca) {
	u64 estimated_speed = 0;
	int i = 0;
	u64 divider = 0;
	u64 j = 1;
	while (i < buffs_size) {
		if (buffer_speed[i] != 0) {
			estimated_speed += j*buffer_speed[i];
			divider+=j;
			j+=1;
		}
		++i;
	}
	if (divider == 0) {
		printk("WTF INSERTED VALUES IS 0 if it should be at least 1");
	}
	else {
		estimated_speed = estimated_speed / divider;
	}
	u64 tt = get_tt();
	printk(KERN_INFO "forecast CWND=?; SPEED=%llu", estimated_speed*tt*1000/ca->curr_rtt);
	return estimated_speed;
}

u64 speed_forecast_moving_average_weighted_2(struct bictcp *ca) {
	u64 estimated_speed = 0;
	int i = 0;
	u64 divider = 0;
	u64 j = 1;
	while (i < buffs_size) {
		if (buffer_speed[i] != 0) {
			estimated_speed += j*j*buffer_speed[i];
			divider+=j*j;
			j+=1;
		}
		++i;
	}
	if (divider == 0) {
		printk("WTF INSERTED VALUES IS 0 if it should be at least 1");
	}
	else {
		estimated_speed = estimated_speed / divider;
	}
	u64 tt = get_tt();
	printk(KERN_INFO "forecast CWND=?; SPEED=%llu", estimated_speed*tt*1000/ca->curr_rtt);
	return estimated_speed;
}

u64 speed_forecast_trend(struct bictcp *ca) {
	u64 estimated_speed = 0;
	int i = 0;
	u64 speed1, speed2;
	speed1 = buffer_speed[buffs_size-2];
	speed2 = buffer_speed[buffs_size-1];
	u64 tt = acked_time[ack_buff_size-1] - acked_time[ack_buff_size-2] * 10 / HZ;

	// y = (x-x1)/(x2-x1)*(y2-y1) + y1
	// x = 3tt
	// x1 = tt
	// x2 = 2tt
	// speed = (2tt)/(tt)*(speed2-speed1)+speed1
	if (speed2 >= speed1) {
		estimated_speed = (2)*(speed2-speed1)+speed1;
	}
	else {
		if (speed1 >= 2* (speed1-speed2)) {
			estimated_speed = speed1 - (2)*(speed1-speed2);
		}
		else estimated_speed = 0;
	}

	printk(KERN_INFO "TREND: %llu %llu %llu", speed1, speed2, estimated_speed);
	printk(KERN_INFO "forecast CWND=?; SPEED=%llu", estimated_speed*tt*1000/ca->curr_rtt);
	return estimated_speed;
}

u32 point_forecast_moving_average_weighted(struct bictcp *ca) {
	int i = 0;
	u64 estimated_speed = 0U;
	u64 error = 0U;
	u64 divider = 0;
	u64 j = 1;

	while (i < buffs_size) {
		if (buffer_speed[i] != 0){
			estimated_speed += j*buffer_speed[i];
			error+=last_mistakes[i];
			divider+=j;
			j+=1;
		}
		
		++i;
	}
	if (divider != 0) {
		estimated_speed = estimated_speed / divider;
	}
	root_mean_square_deviation();
	error = z_index * rms / 100;
	if (error > estimated_speed) {
		error = estimated_speed -1;
	}
	i = 0;

	printk(KERN_INFO "error=%llu; rms=%llu; z_index=%llu", error, rms, z_index);

	printk("BUFFER SPEED: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   buffer_speed[buffs_size-20], buffer_speed[buffs_size-19], buffer_speed[buffs_size-18], buffer_speed[buffs_size-17], buffer_speed[buffs_size-16],
		   buffer_speed[buffs_size-15], buffer_speed[buffs_size-14], buffer_speed[buffs_size-13], buffer_speed[buffs_size-12], buffer_speed[buffs_size-11],
		   buffer_speed[buffs_size-10], buffer_speed[buffs_size-9], buffer_speed[buffs_size-8], buffer_speed[buffs_size-7], buffer_speed[buffs_size-6],
		   buffer_speed[buffs_size-5], buffer_speed[buffs_size-4], buffer_speed[buffs_size-3], buffer_speed[buffs_size-2], buffer_speed[buffs_size-1]
);

	printk("BUFFER ERROR: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   last_mistakes[buffs_size-20], last_mistakes[buffs_size-19], last_mistakes[buffs_size-18], last_mistakes[buffs_size-17], last_mistakes[buffs_size-16],
		   last_mistakes[buffs_size-15], last_mistakes[buffs_size-14], last_mistakes[buffs_size-13], last_mistakes[buffs_size-12], last_mistakes[buffs_size-11],
		   last_mistakes[buffs_size-10], last_mistakes[buffs_size-9], last_mistakes[buffs_size-8], last_mistakes[buffs_size-7], last_mistakes[buffs_size-6],
		   last_mistakes[buffs_size-5], last_mistakes[buffs_size-4], last_mistakes[buffs_size-3], last_mistakes[buffs_size-2], last_mistakes[buffs_size-1]
);	
	
	printk(KERN_INFO "RESTART estimated speed = %llu; step = %llu", estimated_speed, error);
	u64 tt = get_tt();
	go_to_zero();

	printk(KERN_INFO "CURRENT RTT AND TT: %llu; %llu", ca->curr_rtt/1000, tt);
	// return (u32)(estimated_speed - error);
	if (step == 0) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt;
	}
	if (step == 1) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt;
	}
    return 1U;	
}

u32 point_forecast_moving_average_weighted_2(struct bictcp *ca) {
	int i = 0;
	u64 estimated_speed = 0U;
	u64 error = 0U;
	u64 divider = 0;
	u64 j = 1;

	while (i < buffs_size) {
		if (buffer_speed[i] != 0){
			estimated_speed += j*j*buffer_speed[i];
			error+=last_mistakes[i];
			divider+=j*j;
			j+=1;
		}
		
		++i;
	}
	if (divider != 0) {
		estimated_speed = estimated_speed / divider;
	}
	root_mean_square_deviation();
	error = z_index * rms / 100;
	if (error > estimated_speed) {
		error = estimated_speed -1;
	}
	i = 0;

	printk(KERN_INFO "error=%llu; rms=%llu; z_index=%llu", error, rms, z_index);

	printk("BUFFER SPEED: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   buffer_speed[buffs_size-20], buffer_speed[buffs_size-19], buffer_speed[buffs_size-18], buffer_speed[buffs_size-17], buffer_speed[buffs_size-16],
		   buffer_speed[buffs_size-15], buffer_speed[buffs_size-14], buffer_speed[buffs_size-13], buffer_speed[buffs_size-12], buffer_speed[buffs_size-11],
		   buffer_speed[buffs_size-10], buffer_speed[buffs_size-9], buffer_speed[buffs_size-8], buffer_speed[buffs_size-7], buffer_speed[buffs_size-6],
		   buffer_speed[buffs_size-5], buffer_speed[buffs_size-4], buffer_speed[buffs_size-3], buffer_speed[buffs_size-2], buffer_speed[buffs_size-1]
);

	printk("BUFFER ERROR: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   last_mistakes[buffs_size-20], last_mistakes[buffs_size-19], last_mistakes[buffs_size-18], last_mistakes[buffs_size-17], last_mistakes[buffs_size-16],
		   last_mistakes[buffs_size-15], last_mistakes[buffs_size-14], last_mistakes[buffs_size-13], last_mistakes[buffs_size-12], last_mistakes[buffs_size-11],
		   last_mistakes[buffs_size-10], last_mistakes[buffs_size-9], last_mistakes[buffs_size-8], last_mistakes[buffs_size-7], last_mistakes[buffs_size-6],
		   last_mistakes[buffs_size-5], last_mistakes[buffs_size-4], last_mistakes[buffs_size-3], last_mistakes[buffs_size-2], last_mistakes[buffs_size-1]
);	
	
	printk(KERN_INFO "RESTART estimated speed = %llu; step = %llu", estimated_speed, error);
	u64 tt = get_tt();
	go_to_zero();

	printk(KERN_INFO "CURRENT RTT AND TT: %llu; %llu", ca->curr_rtt/1000, tt);
	// return (u32)(estimated_speed - error);

	if (step == 0) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt;
	}
	if (step == 1) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt;
	}
    return 1U;
	
}

u32 point_forecast_moving_average(struct bictcp *ca) {
	int i = 0;
	u64 estimated_speed = 0U;
	u64 error = 0U;
	while (i < buffs_size) {
		estimated_speed += buffer_speed[i];
		error+=last_mistakes[i];
		++i;
	}
	if (inserted_values != 0) {
		estimated_speed = estimated_speed / inserted_values;
	}
	root_mean_square_deviation();
	error = z_index * rms / 100;
	if (error > estimated_speed) {
		error = estimated_speed -1;
	}

	printk(KERN_INFO "error=%llu; rms=%llu; z_index=%llu", error, rms, z_index);

	// printk(KERN_INFO "BUFFER SPEED: %llu %llu %llu", buffer_speed[buffs_size-3], buffer_speed[buffs_size - 2], buffer_speed[buffs_size - 1]);

	// printk(KERN_INFO "BUFFER ERROR: %llu %llu %llu", last_mistakes[buffs_size - 3], last_mistakes[buffs_size - 2], last_mistakes[buffs_size - 1]);
	printk("BUFFER SPEED: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		buffer_speed[buffs_size-20], buffer_speed[buffs_size-19], buffer_speed[buffs_size-18], buffer_speed[buffs_size-17], buffer_speed[buffs_size-16],
		buffer_speed[buffs_size-15], buffer_speed[buffs_size-14], buffer_speed[buffs_size-13], buffer_speed[buffs_size-12], buffer_speed[buffs_size-11],
		buffer_speed[buffs_size-10], buffer_speed[buffs_size-9], buffer_speed[buffs_size-8], buffer_speed[buffs_size-7], buffer_speed[buffs_size-6],
		buffer_speed[buffs_size-5], buffer_speed[buffs_size-4], buffer_speed[buffs_size-3], buffer_speed[buffs_size-2], buffer_speed[buffs_size-1]
);

	printk("BUFFER ERROR: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   last_mistakes[buffs_size-20], last_mistakes[buffs_size-19], last_mistakes[buffs_size-18], last_mistakes[buffs_size-17], last_mistakes[buffs_size-16],
		   last_mistakes[buffs_size-15], last_mistakes[buffs_size-14], last_mistakes[buffs_size-13], last_mistakes[buffs_size-12], last_mistakes[buffs_size-11],
		   last_mistakes[buffs_size-10], last_mistakes[buffs_size-9], last_mistakes[buffs_size-8], last_mistakes[buffs_size-7], last_mistakes[buffs_size-6],
		   last_mistakes[buffs_size-5], last_mistakes[buffs_size-4], last_mistakes[buffs_size-3], last_mistakes[buffs_size-2], last_mistakes[buffs_size-1]
);	
	
	printk(KERN_INFO "RESTART estimated speed = %llu; step = %llu", estimated_speed, error);
	u64 tt = get_tt();
	go_to_zero();

	printk(KERN_INFO "CURRENT RTT AND TT: %llu; %llu", ca->curr_rtt/1000, tt);
	if (step == 0) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt;
	}
	if (step == 1) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt;
	}
    return 1U;

}


u32 point_forecast_trend(struct bictcp *ca) {
	int i = 0;
	u64 estimated_speed = 0U;
	u64 error = 0U;
	while (i < buffs_size) {
		error+=last_mistakes[i];
		++i;
	}
	estimated_speed = speed_forecast_trend(ca);
	root_mean_square_deviation();
	error = z_index * rms / 100;
	if (error > estimated_speed) {
		error = estimated_speed -1;
	}
	printk(KERN_INFO "error=%llu; rms=%llu; z_index=%llu", error, rms, z_index);

	// printk(KERN_INFO "BUFFER SPEED: %llu %llu %llu", buffer_speed[buffs_size-3], buffer_speed[buffs_size - 2], buffer_speed[buffs_size - 1]);

	// printk(KERN_INFO "BUFFER ERROR: %llu %llu %llu", last_mistakes[buffs_size - 3], last_mistakes[buffs_size - 2], last_mistakes[buffs_size - 1]);
	printk("BUFFER SPEED: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   buffer_speed[buffs_size-20], buffer_speed[buffs_size-19], buffer_speed[buffs_size-18], buffer_speed[buffs_size-17], buffer_speed[buffs_size-16],
		   buffer_speed[buffs_size-15], buffer_speed[buffs_size-14], buffer_speed[buffs_size-13], buffer_speed[buffs_size-12], buffer_speed[buffs_size-11],
		   buffer_speed[buffs_size-10], buffer_speed[buffs_size-9], buffer_speed[buffs_size-8], buffer_speed[buffs_size-7], buffer_speed[buffs_size-6],
		   buffer_speed[buffs_size-5], buffer_speed[buffs_size-4], buffer_speed[buffs_size-3], buffer_speed[buffs_size-2], buffer_speed[buffs_size-1]
);

	printk("BUFFER ERROR: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu", 
		   last_mistakes[buffs_size-20], last_mistakes[buffs_size-19], last_mistakes[buffs_size-18], last_mistakes[buffs_size-17], last_mistakes[buffs_size-16],
		   last_mistakes[buffs_size-15], last_mistakes[buffs_size-14], last_mistakes[buffs_size-13], last_mistakes[buffs_size-12], last_mistakes[buffs_size-11],
		   last_mistakes[buffs_size-10], last_mistakes[buffs_size-9], last_mistakes[buffs_size-8], last_mistakes[buffs_size-7], last_mistakes[buffs_size-6],
		   last_mistakes[buffs_size-5], last_mistakes[buffs_size-4], last_mistakes[buffs_size-3], last_mistakes[buffs_size-2], last_mistakes[buffs_size-1]
);	
	
	printk(KERN_INFO "RESTART estimated speed = %llu; step = %llu", estimated_speed, error);
	u64 tt = get_tt();
	go_to_zero();

	printk(KERN_INFO "CURRENT RTT AND TT: %llu; %llu", ca->curr_rtt/1000, tt);
	// return (u32)(estimated_speed - error);
	if (step == 0) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed - error)*tt*1000/ca->curr_rtt;
	}
	if (step == 1) {
		printk(KERN_INFO "forecast CWND=%llu; SPEED=%llu", (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt, estimated_speed*tt*1000/ca->curr_rtt);
		return (u32)(estimated_speed + error)*tt*1000/ca->curr_rtt;
	}
    return 1U;
}

u32 point_forecast_final(struct bictcp *ca) {
	if (forecast_method == 0) {
		return point_forecast_moving_average(ca);
	}
	else if (forecast_method == 1) {
		return point_forecast_moving_average_weighted(ca);
	}
	else if (forecast_method == 2) {
		return point_forecast_trend(ca);
	}
	else if (forecast_method == 3) {
		return point_forecast_moving_average_weighted_2(ca);
	}
	else return point_forecast_moving_average(ca);
}

u64 speed_forecast_final(struct bictcp *ca) {
	if (forecast_method == 0) {
		return speed_forecast_moving_average(ca);
	}
	else if (forecast_method == 1) {
		return speed_forecast_moving_average_weighted(ca);
	}
	else if (forecast_method == 2) {
		return speed_forecast_trend(ca);
	}
	else if (forecast_method == 3) {
		return speed_forecast_moving_average_weighted_2(ca);
	}
	else return speed_forecast_moving_average(ca);
}

static void bictcp_cwnd_event(struct sock *sk, enum tcp_ca_event event)
{
	if (event == CA_EVENT_TX_START) {
		//printk(KERN_INFO "CA_EVENT_TX_START");
		struct bictcp *ca = inet_csk_ca(sk);
		u32 now = tcp_jiffies32;
		s32 delta;

		delta = now - tcp_sk(sk)->lsndtime;

		/* We were application limited (idle) for a while.
		 * Shift epoch_start to keep cwnd growth to cubic curve.
		 */
		if (ca->epoch_start && delta > 0) {
			ca->epoch_start += delta;
			if (after(ca->epoch_start, now))
				ca->epoch_start = now;
		}
		return;
	}
	else if (event == CA_EVENT_CWND_RESTART) {
		printk(KERN_INFO "CA_EVENT_CWND_RESTART");
		struct tcp_sock *tp = tcp_sk(sk);
		struct bictcp *ca = inet_csk_ca(sk);
		tp->prior_cwnd = point_forecast_final(ca);
	}
}

/* calculate the cubic root of x using a table lookup followed by one
 * Newton-Raphson iteration.
 * Avg err ~= 0.195%
 */
static u32 cubic_root(u64 a)
{
	u32 x, b, shift;
	/*
	 * cbrt(x) MSB values for x MSB values in [0..63].
	 * Precomputed then refined by hand - Willy Tarreau
	 *
	 * For x in [0..63],
	 *   v = cbrt(x << 18) - 1
	 *   cbrt(x) = (v[x] + 10) >> 6
	 */
	static const u8 v[] = {
		/* 0x00 */    0,   54,   54,   54,  118,  118,  118,  118,
		/* 0x08 */  123,  129,  134,  138,  143,  147,  151,  156,
		/* 0x10 */  157,  161,  164,  168,  170,  173,  176,  179,
		/* 0x18 */  181,  185,  187,  190,  192,  194,  197,  199,
		/* 0x20 */  200,  202,  204,  206,  209,  211,  213,  215,
		/* 0x28 */  217,  219,  221,  222,  224,  225,  227,  229,
		/* 0x30 */  231,  232,  234,  236,  237,  239,  240,  242,
		/* 0x38 */  244,  245,  246,  248,  250,  251,  252,  254,
	};

	b = fls64(a);
	if (b < 7) {
		/* a in [0..63] */
		return ((u32)v[(u32)a] + 35) >> 6;
	}

	b = ((b * 84) >> 8) - 1;
	shift = (a >> (b * 3));

	x = ((u32)(((u32)v[shift] + 10) << b)) >> 6;

	/*
	 * Newton-Raphson iteration
	 *                         2
	 * x    = ( 2 * x  +  a / x  ) / 3
	 *  k+1          k         k
	 */
	x = (2 * x + (u32)div64_u64(a, (u64)x * (u64)(x - 1)));
	x = ((x * 341) >> 10);
	return x;
}

/*
 * Compute congestion window to use.
 */
static inline void bictcp_update(struct bictcp *ca, u32 cwnd, u32 acked)
{
	u32 delta, bic_target, max_cnt;
	u64 offs, t;
	printk(KERN_INFO "UPDATE cwnd = %u", cwnd);
	ca->ack_cnt += acked;	/* count the number of ACKed packets */
	new_acked += acked;

	if (new_acked >= (u64)(packet_limit)) {
		// all_acked+=new_acked;
		int i = 0; 
		while (i < ack_buff_size - 1) {
			acked_buffer[i] = acked_buffer[i+1];
			acked_time[i] = acked_time[i+1];
			i+=1;
		}
		acked_buffer[ack_buff_size-1] = new_acked;
		acked_time[ack_buff_size-1] = jiffies;
		if (!estim_round_started) {
			int j = 0;
			while (j < ack_buff_size - 1) {
				acked_time[j] = acked_time[ack_buff_size-1]; //all fields are point to current time now for correct calculation of all_time variable
				++j;
			}
			estim_round_started = true;
		}
		printk(KERN_INFO "acked packets %llu at time %llu", new_acked, jiffies);
	
		new_acked = 0;
		count+=1;
	}
	if (count == 10) {
		// all_acked = 0;
		int i = 0;
		count=0;
		printk(KERN_INFO "acked buffer: %llu %llu %llu %llu %llu %llu %llu %llu", acked_buffer[ack_buff_size-8], acked_buffer[ack_buff_size-7], acked_buffer[ack_buff_size-6], acked_buffer[ack_buff_size-5], acked_buffer[ack_buff_size-4], acked_buffer[ack_buff_size-3], acked_buffer[ack_buff_size-2], acked_buffer[ack_buff_size-1]);
		u64 new_speed = 0;
		while (i < ack_buff_size) {
			new_speed+=acked_buffer[i];
			i+=1;
		}
		i = 0;
		u64 all_time = get_tt();
		if (all_time == 0) {
			printk(KERN_INFO "wtf time is zero");
			all_time = 1;
		}
		printk(KERN_INFO "all_time and all packets: %llu %llu", all_time, new_speed);

		new_speed = new_speed / all_time;
		printk(KERN_INFO "new speed = %llu", new_speed);
		while (i < buffs_size-1) {
			buffer_speed[i] = buffer_speed[i+1];
			last_mistakes[i] = last_mistakes[i+1];
			++i;
		}
		i = 0;
		buffer_speed[buffs_size-1] = new_speed;
		if (inserted_values < buffs_size) {
			inserted_values+=1;
		}
		if (new_speed >= new_estimated_speed) {
			last_mistakes[buffs_size-1] = new_speed - new_estimated_speed;
		}
		else {
			last_mistakes[buffs_size-1] = new_estimated_speed - new_speed;
		}
		if ((inserted_values == 1 && (forecast_method == 0 || forecast_method == 1 || forecast_method == 3)) || 
			(inserted_values <= 2 && (forecast_method == 2))) {
			//then error should be zero because we didn't even forecast the first value
			last_mistakes[buffs_size-1] = 0;
		}
		
		u64 estimated_speed = speed_forecast_final(ca);	
		printk(KERN_INFO "buffer_speed_last = %llu error = %llu forecast = %llu", new_speed, last_mistakes[buffs_size-1], new_estimated_speed);
		new_estimated_speed = estimated_speed;
		// i = 0;
		// while (i < ack_buff_size) {
		// 	acked_buffer[i] = 0U;
		// 	acked_time[i] = 0U;
		// 	++i;	
		// }
	}
	
	if (ca->last_cwnd == cwnd &&
	    (s32)(tcp_jiffies32 - ca->last_time) <= HZ / 32)
		return;

	/* The CUBIC function can update ca->cnt at most once per jiffy.
	 * On all cwnd reduction events, ca->epoch_start is set to 0,
	 * which will force a recalculation of ca->cnt.
	 */
	if (ca->epoch_start && tcp_jiffies32 == ca->last_time)
		goto tcp_friendliness;

	ca->last_cwnd = cwnd;
	ca->last_time = tcp_jiffies32;

	if (ca->epoch_start == 0) {
		ca->epoch_start = tcp_jiffies32;	/* record beginning */
		ca->ack_cnt = acked;			/* start counting */
		ca->tcp_cwnd = cwnd;			/* syn with cubic */

		if (ca->last_max_cwnd <= cwnd) {
			ca->bic_K = 0;
			ca->bic_origin_point = cwnd;
		} else {
			/* Compute new K based on
			 * (wmax-cwnd) * (srtt>>3 / HZ) / c * 2^(3*bictcp_HZ)
			 */
			ca->bic_K = cubic_root(cube_factor
					       * (ca->last_max_cwnd - cwnd));
			ca->bic_origin_point = ca->last_max_cwnd;
		}
	}

	/* cubic function - calc*/
	/* calculate c * time^3 / rtt,
	 *  while considering overflow in calculation of time^3
	 * (so time^3 is done by using 64 bit)
	 * and without the support of division of 64bit numbers
	 * (so all divisions are done by using 32 bit)
	 *  also NOTE the unit of those veriables
	 *	  time  = (t - K) / 2^bictcp_HZ
	 *	  c = bic_scale >> 10
	 * rtt  = (srtt >> 3) / HZ
	 * !!! The following code does not have overflow problems,
	 * if the cwnd < 1 million packets !!!
	 */

	t = (s32)(tcp_jiffies32 - ca->epoch_start);
	t += usecs_to_jiffies(ca->delay_min);
	/* change the unit from HZ to bictcp_HZ */
	t <<= BICTCP_HZ;
	do_div(t, HZ);

	if (t < ca->bic_K)		/* t - K */
		offs = ca->bic_K - t;
	else
		offs = t - ca->bic_K;

	/* c/rtt * (t-K)^3 */
	delta = (cube_rtt_scale * offs * offs * offs) >> (10+3*BICTCP_HZ);
	if (t < ca->bic_K)                            /* below origin*/
		bic_target = ca->bic_origin_point - delta;
	else                                          /* above origin*/
		bic_target = ca->bic_origin_point + delta;

	/* cubic function - calc bictcp_cnt*/
	if (bic_target > cwnd) {
		ca->cnt = cwnd / (bic_target - cwnd);
	} else {
		ca->cnt = 100 * cwnd;              /* very small increment*/
	}

	/*
	 * The initial growth of cubic function may be too conservative
	 * when the available bandwidth is still unknown.
	 */
	if (ca->last_max_cwnd == 0 && ca->cnt > 20)
		ca->cnt = 20;	/* increase cwnd 5% per RTT */

tcp_friendliness:
	/* TCP Friendly */
	if (tcp_friendliness) {
		u32 scale = beta_scale;

		delta = (cwnd * scale) >> 3;
		while (ca->ack_cnt > delta) {		/* update tcp cwnd */
			ca->ack_cnt -= delta;
			ca->tcp_cwnd++;
		}

		if (ca->tcp_cwnd > cwnd) {	/* if bic is slower than tcp */
			delta = ca->tcp_cwnd - cwnd;
			max_cnt = cwnd / delta;
			if (ca->cnt > max_cnt)
				ca->cnt = max_cnt;
		}
	}
	/* The maximum rate of cwnd increase CUBIC allows is 1 packet per
	 * 2 packets ACKed, meaning cwnd grows at 1.5x per RTT.
	 */
	ca->cnt = max(ca->cnt, 2U);
}

static void bictcp_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct bictcp *ca = inet_csk_ca(sk);

	if (!tcp_is_cwnd_limited(sk))
		return;

	if (tcp_in_slow_start(tp)) {
		if (hystart && after(ack, ca->end_seq))
			bictcp_hystart_reset(sk);
		acked = tcp_slow_start(tp, acked);
		if (!acked)
			return;
	}
	bictcp_update(ca, tp->snd_cwnd, acked);
	tcp_cong_avoid_ai(tp, ca->cnt, acked);
}

static u32 bictcp_recalc_ssthresh(struct sock *sk)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	struct bictcp *ca = inet_csk_ca(sk);
	printk(KERN_INFO "RECALC SSTHRESH");
	// printk(KERN_INFO "buffer_speed_last = %llu error = %llu forecast = %llu", new_speed, last_mistakes[buffs_size-1], new_estimated_speed);
	ca->epoch_start = 0;	/* end of epoch */
	u32 result = 0;

	u32 vityas = point_forecast_final(ca);
	printk(KERN_INFO "Returning max of (2, vityas=%llu), but cubic could be %u", vityas, tp->snd_cwnd * beta / BICTCP_BETA_SCALE);
	result = max(2U, vityas);
	/* Wmax and fast convergence */
	if (tp->snd_cwnd < ca->last_max_cwnd && fast_convergence)
		ca->last_max_cwnd = (tp->snd_cwnd * (BICTCP_BETA_SCALE + beta))
			/ (2 * BICTCP_BETA_SCALE);
	else
		ca->last_max_cwnd = tp->snd_cwnd;
	// printk(KERN_INFO "Returning max of (cubic=%u, 2, vityas=%u)", (tp->snd_cwnd * beta) / BICTCP_BETA_SCALE, estimated_speed - (u32)(error));
	// result = max(max((tp->snd_cwnd * beta) / BICTCP_BETA_SCALE, 2U), estimated_speed - (u32)(error));
	return result;
}

static void bictcp_state(struct sock *sk, u8 new_state)
{
	if (new_state == TCP_CA_Loss) {
		bictcp_reset(inet_csk_ca(sk));
		bictcp_hystart_reset(sk);
	}
}

/* Account for TSO/GRO delays.
 * Otherwise short RTT flows could get too small ssthresh, since during
 * slow start we begin with small TSO packets and ca->delay_min would
 * not account for long aggregation delay when TSO packets get bigger.
 * Ideally even with a very small RTT we would like to have at least one
 * TSO packet being sent and received by GRO, and another one in qdisc layer.
 * We apply another 100% factor because @rate is doubled at this point.
 * We cap the cushion to 1ms.
 */
static u32 hystart_ack_delay(struct sock *sk)
{
	unsigned long rate;

	rate = READ_ONCE(sk->sk_pacing_rate);
	if (!rate)
		return 0;
	return min_t(u64, USEC_PER_MSEC,
		     div64_ul((u64)GSO_MAX_SIZE * 4 * USEC_PER_SEC, rate));
}

static void hystart_update(struct sock *sk, u32 delay)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct bictcp *ca = inet_csk_ca(sk);
	u32 threshold;

	if (hystart_detect & HYSTART_ACK_TRAIN) {
		u32 now = bictcp_clock_us(sk);

		/* first detection parameter - ack-train detection */
		if ((s32)(now - ca->last_ack) <= hystart_ack_delta_us) {
			ca->last_ack = now;

			threshold = ca->delay_min + hystart_ack_delay(sk);

			/* Hystart ack train triggers if we get ack past
			 * ca->delay_min/2.
			 * Pacing might have delayed packets up to RTT/2
			 * during slow start.
			 */
			if (sk->sk_pacing_status == SK_PACING_NONE)
				threshold >>= 1;

			if ((s32)(now - ca->round_start) > threshold) {
				ca->found = 1;
				pr_debug("hystart_ack_train (%u > %u) delay_min %u (+ ack_delay %u) cwnd %u\n",
					 now - ca->round_start, threshold,
					 ca->delay_min, hystart_ack_delay(sk), tp->snd_cwnd);
				NET_INC_STATS(sock_net(sk),
					      LINUX_MIB_TCPHYSTARTTRAINDETECT);
				NET_ADD_STATS(sock_net(sk),
					      LINUX_MIB_TCPHYSTARTTRAINCWND,
					      tp->snd_cwnd);
				tp->snd_ssthresh = tp->snd_cwnd;
			}
		}
	}

	if (hystart_detect & HYSTART_DELAY) {
		/* obtain the minimum delay of more than sampling packets */
		if (ca->curr_rtt > delay)
			ca->curr_rtt = delay;
		if (ca->sample_cnt < HYSTART_MIN_SAMPLES) {
			ca->sample_cnt++;
		} else {
			if (ca->curr_rtt > ca->delay_min +
			    HYSTART_DELAY_THRESH(ca->delay_min >> 3)) {
				ca->found = 1;
				NET_INC_STATS(sock_net(sk),
					      LINUX_MIB_TCPHYSTARTDELAYDETECT);
				NET_ADD_STATS(sock_net(sk),
					      LINUX_MIB_TCPHYSTARTDELAYCWND,
					      tp->snd_cwnd);
				tp->snd_ssthresh = tp->snd_cwnd;
			}
		}
	}
}

static void bictcp_acked(struct sock *sk, const struct ack_sample *sample)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	struct bictcp *ca = inet_csk_ca(sk);
	u32 delay;

	/* Some calls are for duplicates without timetamps */
	if (sample->rtt_us < 0)
		return;

	/* Discard delay samples right after fast recovery */
	if (ca->epoch_start && (s32)(tcp_jiffies32 - ca->epoch_start) < HZ)
		return;

	delay = sample->rtt_us;
	if (delay == 0)
		delay = 1;

	/* first time call or link delay decreases */
	if (ca->delay_min == 0 || ca->delay_min > delay)
		ca->delay_min = delay;

	/* hystart triggers when cwnd is larger than some threshold */
	if (!ca->found && tcp_in_slow_start(tp) && hystart &&
	    tp->snd_cwnd >= hystart_low_window)
		hystart_update(sk, delay);
}

static struct tcp_congestion_ops vityastcp __read_mostly = {
	.init		= bictcp_init,
	.ssthresh	= bictcp_recalc_ssthresh,
	.cong_avoid	= bictcp_cong_avoid,
	.set_state	= bictcp_state,
	.undo_cwnd	= tcp_reno_undo_cwnd,
	.cwnd_event	= bictcp_cwnd_event,
	.pkts_acked = bictcp_acked,
	.owner		= THIS_MODULE,
	.name		= "vityas",
};

static int __init vityastcp_register(void)
{
	BUILD_BUG_ON(sizeof(struct bictcp) > ICSK_CA_PRIV_SIZE);
	printk(KERN_INFO "Vityas test loaded");
	go_to_zero();
	int i = 0;
	while (i < ack_buff_size) {
		acked_buffer[i] = 0U;
		acked_time[i] = 0U;
		++i;	
	}

	printk(KERN_INFO "Probability = %d Packet_limit = %d forecast_method = %d Step_type = %d", probability, packet_limit, forecast_method, step);
	// printk(KERN_INFO "init acked_buf %llu %llu", acked_buffer[0], acked_time[0]);

	if (probability == 90) {
		z_index = 165; //1.65
	}
	else if (probability == 80) {
		z_index = 128;
	}
	else if (probability == 70) {
		z_index = 104;
	}
	else if (probability == 60) {
		z_index = 85;
	}
	else if (probability == 45) {
		z_index = 60;
	}
	else if (probability == 30) {
		z_index = 38;
	}
	else if (probability == 20) {
		z_index = 24;
	}
	else if (probability == 10) {
		z_index = 13;
	}
	else {
		z_index = 100;
	}

	/* Precompute a bunch of the scaling factors that are used per-packet
	 * based on SRTT of 100ms
	 */

	beta_scale = 8*(BICTCP_BETA_SCALE+beta) / 3
		/ (BICTCP_BETA_SCALE - beta);

	cube_rtt_scale = (bic_scale * 10);	/* 1024*c/rtt */

	/* calculate the "K" for (wmax-cwnd) = c/rtt * K^3
	 *  so K = cubic_root( (wmax-cwnd)*rtt/c )
	 * the unit of K is bictcp_HZ=2^10, not HZ
	 *
	 *  c = bic_scale >> 10
	 *  rtt = 100ms
	 *
	 * the following code has been designed and tested for
	 * cwnd < 1 million packets
	 * RTT < 100 seconds
	 * HZ < 1,000,00  (corresponding to 10 nano-second)
	 */

	/* 1/c * 2^2*bictcp_HZ * srtt */
	cube_factor = 1ull << (10+3*BICTCP_HZ); /* 2^40 */

	/* divide by bic_scale and by constant Srtt (100ms) */
	do_div(cube_factor, bic_scale * 10);

	return tcp_register_congestion_control(&vityastcp);
}

static void __exit vityastcp_unregister(void)
{
	printk(KERN_INFO "Vityas test exit");
	tcp_unregister_congestion_control(&vityastcp);
}

module_init(vityastcp_register);
module_exit(vityastcp_unregister);

MODULE_AUTHOR("Vityas");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Vityas TCP TEST");
MODULE_VERSION("1.0");