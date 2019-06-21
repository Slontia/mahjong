import tensorflow as tf
from buffer import MahjongBufferFrost2
import numpy as np
from datetime import datetime
import scipy.special as scisp
import MahjongPy as mp

class MahjongNetFrost2():
    """
    Mahjong Network Frost 2
    Using CNN + FC layers, purely feed-forward network
    """
    def __init__(self, graph, agent_no, lr=3e-4, log_dir="../log/", num_tile_type=34, num_each_tile=58, num_vf=29, value_base=10000.0):
        """Model function for CNN."""

        self.session = tf.Session(graph=graph)
        self.graph = graph
        self.log_dir = log_dir + ('' if log_dir[-1]=='/' else '/')
        self.value_base = value_base

        self.num_tile_type = num_tile_type  # number of tile types
        self.num_each_tile = num_each_tile # number of features for each tile
        self.num_vf = num_vf # number of vector features

        with self.graph.as_default():

            self.matrix_features = tf.placeholder(dtype=tf.float32, shape=[None, self.num_tile_type, self.num_each_tile], name='Features')
            self.vector_features = tf.placeholder(dtype=tf.float32, shape=[None, self.num_vf], name='Features')

            with tf.variable_scope('trained_net'):
                # Convolutional Layer #1
                conv1 = tf.layers.conv1d(
                    inputs=self.matrix_features,
                    filters=256,
                    kernel_size=3,
                    strides=1,
                    padding="same",
                    activation=tf.nn.relu)

                # Convolutional Layer #2 and Pooling Layer #2
                conv2 = tf.layers.conv1d(
                    inputs=conv1,
                    filters=128,
                    kernel_size=3,
                    strides=3,
                    padding="same",
                    activation=tf.nn.relu)

                # Convolutional Layer #2 and Pooling Layer #2
                conv3 = tf.layers.conv1d(
                    inputs=conv2,
                    filters=128,
                    kernel_size=1,
                    strides=3,
                    padding="same",
                    activation=tf.nn.relu)

                # Dense Layers
                flat = tf.concat([tf.layers.flatten(conv3), self.vector_features], axis=1)
                fc1 = tf.layers.dense(inputs=flat, units=128, activation=tf.nn.relu)
                fc2 = tf.layers.dense(inputs=fc1, units=256, activation=tf.nn.relu)
                fc3 = tf.layers.dense(inputs=fc2, units=128, activation=tf.nn.relu)

                # dropout = tf.layers.dropout(
                #     inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

                self.value_output = tf.layers.dense(inputs=fc3, units=1, activation=None)

            with tf.variable_scope('target_net'):
                # Convolutional Layer #1
                conv1 = tf.layers.conv1d(
                    inputs=self.matrix_features,
                    filters=256,
                    kernel_size=3,
                    strides=1,
                    padding="same",
                    activation=tf.nn.relu)

                # Convolutional Layer #2 and Pooling Layer #2
                conv2 = tf.layers.conv1d(
                    inputs=conv1,
                    filters=128,
                    kernel_size=3,
                    strides=3,
                    padding="same",
                    activation=tf.nn.relu)

                # Convolutional Layer #2 and Pooling Layer #2
                conv3 = tf.layers.conv1d(
                    inputs=conv2,
                    filters=128,
                    kernel_size=1,
                    strides=3,
                    padding="same",
                    activation=tf.nn.relu)

                # Dense Layers
                flat = tf.concat([tf.layers.flatten(conv3), self.vector_features], axis=1)
                fc1 = tf.layers.dense(inputs=flat, units=128, activation=tf.nn.relu)
                fc2 = tf.layers.dense(inputs=fc1, units=256, activation=tf.nn.relu)
                fc3 = tf.layers.dense(inputs=fc2, units=128, activation=tf.nn.relu)

                # dropout = tf.layers.dropout(
                #     inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

                self.value_output_tarnet = tf.layers.dense(inputs=fc3, units=1, activation=None)

            self.value_target = tf.placeholder(dtype=tf.float32, shape=[None, 1], name='value_targets')

            self.loss = tf.losses.mean_squared_error(self.value_target / value_base, self.value_output / value_base)
            self.optimizer = tf.train.AdamOptimizer(lr)
            self.train_step = self.optimizer.minimize(self.loss)

            self.saver = tf.train.Saver()

            tf.summary.scalar('loss', self.loss)
            tf.summary.histogram('value_pred', self.value_output)

            now = datetime.now()
            datetime_str = now.strftime("%Y%m%d-%H%M%S")

            self.merged = tf.summary.merge_all()
            self.train_writer = tf.summary.FileWriter(log_dir + 'naiveAIlog-Agent{}-'.format(agent_no) + datetime_str, self.session.graph)

            t_params = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='target_net')
            e_params = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='trained_net')
            self.cg = [tf.assign(t, e) for t, e in zip(t_params, e_params)]
            self.sut = [tf.assign(t, 0.001 * e + 0.999 * t) for t, e in zip(t_params, e_params)]

            self.session.run(tf.global_variables_initializer())

    def sync(self):
        ## Synchronize target network and trained networ
        self.session.run(self.cg)

    def soft_update_tarnet(self):
        self.session.run(self.sut)

    def save(self, model_dir):
        save_path = self.saver.save(self.session, self.log_dir + model_dir + ('' if model_dir[-1]=='/' else '/') + "naiveAI.ckpt")
        print("Model saved in path: %s" % save_path)

    def restore(self, model_path):
        self.saver.restore(self.session, model_path)
        print("Model restored from" + model_path)

    def output(self, input):
        with self.graph.as_default():
            value_pred = self.session.run(self.value_output, feed_dict={self.matrix_features: input[0], self.vector_features: input[1]})

        return value_pred

    def output_tarnet(self, input):
        with self.graph.as_default():
            value_pred = self.session.run(self.value_output_tarnet, feed_dict={self.matrix_features: input[0], self.vector_features: input[1]})

        return value_pred

    def train(self, input, target, logging, global_step):
        with self.graph.as_default():
            loss, _ , summary = self.session.run([self.loss, self.train_step, self.merged],
                feed_dict = {self.matrix_features: input[0], self.vector_features: input[1], self.value_target: target})

            if logging:
                self.train_writer.add_summary(summary, global_step=global_step)

        return loss

class AgentFrost2():
    """
    Mahjong AI agent with PER
    """
    def __init__(self, nn: MahjongNetFrost2, memory:MahjongBufferFrost2, gamma=0.9999, greedy=1.0, lambd=0.975, alpha=0.99,
                 num_tile_type=34, num_each_tile=55, num_vf=29):
        self.nn = nn
        self.gamma = gamma  # discount factor
        self.greedy = greedy
        self.memory = memory
        self.lambd = lambd
        self.alpha = alpha # for Ret-GRAPE
        self.global_step = 0
        self.num_tile_type = num_tile_type  # number of tile types
        self.num_each_tile = num_each_tile # number of features for each tile
        self.num_vf = num_vf # number of vector features

        # statistics
        self.stat = {}
        self.stat['num_games'] = 0.
        self.stat['hora_games'] = 0.
        self.stat['ron_games'] = 0.
        self.stat['tsumo_games'] = 0.
        self.stat['fire_games'] = 0.
        self.stat['total_scores_get'] = 0.

        self.stat['hora_rate'] = 0.
        self.stat['tsumo_rate'] = 0.
        self.stat['fire_rate'] = 0.
        self.stat['fulu_rate'] = 0.
        self.stat['riichi_rate'] = 0.
        self.stat['avg_point_get'] = 0.

        self.stat['hora'] = []
        self.stat['ron'] = []
        self.stat['tsumo'] = []
        self.stat['fire'] = []
        self.stat['score_change'] = []

    def statistics(self, playerNo, result, final_score_change, turn, riichi, menchin):

        fulu = 1 - menchin

        if result.result_type == mp.ResultType.RonAgari:
            ron_playerNo = np.argmax(final_score_change)
            if playerNo == ron_playerNo:
                self.stat['hora_games'] += 1
                self.stat['ron_games'] += 1
                self.stat['total_scores_get'] += np.max(final_score_change)
                self.stat['ron'].append(1)
                self.stat['tsumo'].append(0)
                self.stat['hora'].append(1)
                self.stat['fire'].append(0)
            elif riichi * 1000 + final_score_change[playerNo] < 0 and final_score_change[playerNo] <= - (
                    np.max(final_score_change) - riichi * 1000):
                self.stat['ron'].append(0)
                self.stat['tsumo'].append(0)
                self.stat['hora'].append(0)
                self.stat['fire'].append(1)
                self.stat['fire_games'] += 1

        if result.result_type == mp.ResultType.TsumoAgari:
            tsumo_playerNo = np.argmax(final_score_change)
            if playerNo == tsumo_playerNo:
                self.stat['hora_games'] += 1
                self.stat['tsumo_games'] += 1
                self.stat['total_scores_get'] += np.max(final_score_change)
                self.stat['ron'].append(0)
                self.stat['tsumo'].append(1)
                self.stat['hora'].append(1)
                self.stat['fire'].append(0)

        self.stat['score_change'].append(final_score_change[playerNo])
        self.stat['num_games'] += 1

        self.stat['hora_rate'] = self.stat['hora_games'] / self.stat['num_games']
        self.stat['tsumo_rate'] = self.stat['tsumo_games'] / self.stat['num_games']
        self.stat['fire_rate'] = self.stat['fire_games'] / self.stat['num_games']

        self.stat['fulu_rate'] = (self.stat['fulu_rate'] * (self.stat['hora_games'] - 1) + riichi) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0
        self.stat['riichi_rate'] = (self.stat['riichi_rate'] * (self.stat['hora_games'] - 1) + fulu) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0

        self.stat['hora_turn'] = (self.stat['hora_turn'] * (self.stat['hora_games'] - 1) + turn) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0
        self.stat['avg_point_get'] = self.stat['total_scores_get'] / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0


    def select(self, aval_next_states):
        """
        select an action according to the value estimation of the next state after performing an action
        :param:
            aval_next_states: (matrix_features [N by self.num_tile_type by self.num_each_tile], vector features [N by self.num_vf]), where N is number of possible
                actions (corresponds to aval_next_states)
        :return:
            action: an int number, indicating the index of being selected action,from [0, 1, ..., N]
            policy: an N-dim vector, indicating the probabilities of selecting actions [0, 1, ..., N]
        """
        if aval_next_states is None:
            return None

        aval_next_matrix_features = np.reshape(aval_next_states[0], [-1, self.num_tile_type, self.num_each_tile])
        aval_next_vector_features = np.reshape(aval_next_states[1], [-1, self.num_vf])

        next_value_pred = np.reshape(self.nn.output((aval_next_matrix_features, aval_next_vector_features)), [-1])

        # softmax policy
        policy = scisp.softmax(self.greedy * next_value_pred)

        policy /= policy.sum()

        action = np.random.choice(np.size(policy), p=policy)

        return action, policy

    def remember_episode(self, num_aval_actions, next_matrix_features, next_vector_features, rewards, dones, actions, behavior_policies, weight):
        # try:

        if len(dones) == 0:
            print("Episode Length 0! Not recorded!")
        else:
            self.memory.append_episode(num_aval_actions,
                                       next_matrix_features,
                                       next_vector_features,
                                       np.reshape(rewards, [-1,]),
                                       np.reshape(dones, [-1,]),
                                       np.reshape(actions, [-1]),
                                       np.reshape(behavior_policies, [-1, 40]),
                                       weight=weight)
        # except:
        #     print("Episode Length 0! Not recorded!")
    def learn(self, symmetric_hand=None, episode_start=1, care_lose=True, logging=True):

        if self.memory.filled_size >= episode_start:
            n_t, Sp, sp, r_t, done_t, a_t, mu_t, length, e_index, e_weight = self.memory.sample_episode()

            l = length

            # this_Sp = np.zeros([l, self.num_tile_type, self.num_each_tile], dtype=np.float32)
            # this_sp = np.zeros([l, self.num_vf], dtype=np.float32)

            this_Sp = Sp[np.arange(l), a_t].astype(np.float32)
            this_sp = sp[np.arange(l), a_t].astype(np.float32)

            if not care_lose:
                r_t = np.maximum(r_t, 0)

            mu_size = mu_t.shape[1]

            # _, policy_all = self.select((Sp.reshape([-1, self.num_tile_type, self.num_each_tile]), sp.reshape([-1, self.num_vf])))
            # pi = policy_all.reshape([l, -1])

            q_tar = self.nn.output_tarnet(
                (Sp.reshape([-1, self.num_tile_type, self.num_each_tile]), sp.reshape([-1, self.num_vf]))).reshape(
                [l, mu_size])
            q = self.nn.output(
                (Sp.reshape([-1, self.num_tile_type, self.num_each_tile]), sp.reshape([-1, self.num_vf]))).reshape(
                [l, mu_size])

            for t in range(l):
                q[t, n_t[t]:] = - np.inf  # for computing policy
                q_tar[t, n_t[t]:] = 0

            pi = scisp.softmax(q, axis=1)  # to get the true pi

            pi_t, pi_tp1 = pi, np.concatenate((pi[1:, :], np.zeros([1, mu_size])), axis=0)
            q_t, q_tp1 = q_tar, np.concatenate((q_tar[1:, :], np.zeros([1, mu_size])), axis=0)
            q_t_a = q_t[np.arange(l), a_t]
            v_t, v_tp1 = np.sum(pi_t * q_t, axis=1), np.sum(pi_tp1 * q_tp1, axis=1)
            q_t_a_est = r_t + (1. - done_t) * self.gamma * v_tp1
            td_error = q_t_a_est - q_t_a + self.alpha * (q_t_a - v_t)
            rho_t_a = pi_t[np.arange(l), a_t] / mu_t[np.arange(l), a_t]   # importance sampling ratios
            c_t_a = self.lambd * np.minimum(rho_t_a, 1)

            # print('td_eror')
            # print(td_error[-5:])

            y_prime = 0  # y'_t
            g_q = np.zeros([l])
            for u in reversed(range(l)):  # l-1, l-2, l-3, ..., 0
                # If s_tp1[u] is from an episode different from s_t[u], y_prime needs to be reset.

                y_prime = 0 if done_t[u] else y_prime  # y'_u
                g_q[u] = q_t_a_est[u] + y_prime

                # y'_{u-1} used in the next step
                y_prime = self.lambd * self.gamma * np.minimum(rho_t_a[u], 1) * td_error[u] + self.gamma * c_t_a[u] * y_prime

            target_q = g_q + self.alpha * (q_t_a - v_t)
            target_q = target_q.reshape([l, 1])
            # this_Sp = np.zeros([r.shape[0], self.num_tile_type, self.num_each_tile], dtype=np.float32)
            # this_sp = np.zeros([r.shape[0], self.num_vf], dtype=np.float32)
            # target_q = np.zeros([r.shape[0], 1], dtype=np.float32)
            #
            # episode_length = r.shape[0]
            #
            # td_prime = 0
            #
            # q_all = self.nn.output((Sp, sp))
            #
            # _, policy_all = self.select((Sp.reshape([-1, self.num_tile_type, self.num_each_tile]), sp.reshape([-1, self.num_vf])))
            # policy_all = policy_all.reshape([episode_length, -1])
            #
            # for t in reversed(range(episode_length)):  #Q(lambda)
            #
            #     this_Sp[t] = Sp[t, a[t]]
            #     this_sp[t] = sp[t, a[t]]
            #
            #     q_all_t = q_all[t, 0:n[t]]
            #     q_t_a = q_all_t[a[t], :]
            #
            #     mu_t_a = mu[t, a[t]]
            #     pi_t_a = policy_all[t, a[t]]
            #
            #     if d[t]:
            #         q_t_a_est = r[t]
            #     else:
            #         q_all_tp1 = q_all[t+1, 0:n[t+1]]
            #         policy_tp1 = policy_all[t+1, 0:n[t+1]]
            #         v_tp1 = np.sum(policy_tp1.reshape([n[t+1]]) * q_all_tp1.reshape([n[t+1]]))
            #         q_t_a_est = r[t] + self.gamma * v_tp1
            #
            #     rho_t_a = pi_t_a / mu_t_a
            #     c_t_a = self.lambd * np.minimum(rho_t_a, 1)
            #
            #     td_error_t = q_t_a_est - q_t_a
            #
            #     if d[t]:
            #         td_prime = 0
            #     else:
            #         td_prime = td_prime
            #
            #     target_q[t] = q_t_a_est + td_prime
            #
            #     td_prime = self.gamma * c_t_a * (td_error_t + td_prime)

            # print('target_q')
            # print(target_q[-5:,0])

            self.global_step += 1

            # also train symmetric hand
            if not symmetric_hand == None:
                all_Sp = np.concatenate([symmetric_hand(this_Sp) for _ in range(5)], axis=0).astype(np.float32)
                all_sp = np.concatenate([this_sp for _ in range(5)], axis=0).astype(np.float32)
                all_target_value = np.concatenate([target_q for _ in range(5)], axis=0).astype(np.float32)
            else:
                all_Sp = this_Sp
                all_sp = this_sp
                all_target_value = target_q

            self.nn.train((all_Sp, all_sp), all_target_value, logging=logging, global_step=self.global_step)
            self.nn.soft_update_tarnet()

        else:
            pass

