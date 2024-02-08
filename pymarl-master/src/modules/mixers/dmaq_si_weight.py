import torch as th
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class DMAQ_SI_Weight(nn.Module):
    def __init__(self, args):
        super(DMAQ_SI_Weight, self).__init__()

        self.args = args
        self.n_agents = args.n_agents
        self.n_actions = args.n_actions
        self.state_dim = int(np.prod(args.state_shape))
        self.action_dim = args.n_agents * self.n_actions
        self.state_action_dim = self.state_dim + self.action_dim

        self.num_kernel = args.num_kernel

        self.key_extractors = nn.ModuleList()
        self.agents_extractors = nn.ModuleList()
        self.action_extractors = nn.ModuleList()

        adv_hypernet_embed = self.args.adv_hypernet_embed
        for i in range(self.num_kernel):  # multi-head attention
            if getattr(args, "adv_hypernet_layers", 1) == 1:
                self.key_extractors.append(nn.Linear(self.state_dim, 1))  # key
                self.agents_extractors.append(nn.Linear(self.state_dim, self.n_agents))  # agent
                self.action_extractors.append(nn.Linear(self.state_action_dim, self.n_agents))  # action
            elif getattr(args, "adv_hypernet_layers", 1) == 2:
                self.key_extractors.append(nn.Sequential(nn.Linear(self.state_dim, adv_hypernet_embed),
                                                         nn.ReLU(),
                                                         nn.Linear(adv_hypernet_embed, 1)))  # key
                self.agents_extractors.append(nn.Sequential(nn.Linear(self.state_dim, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, self.n_agents)))  # agent
                self.action_extractors.append(nn.Sequential(nn.Linear(self.state_action_dim, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, self.n_agents)))  # action
            elif getattr(args, "adv_hypernet_layers", 1) == 3:
                self.key_extractors.append(nn.Sequential(nn.Linear(self.state_dim, adv_hypernet_embed),
                                                         nn.ReLU(),
                                                         nn.Linear(adv_hypernet_embed, adv_hypernet_embed),
                                                         nn.ReLU(),
                                                         nn.Linear(adv_hypernet_embed, 1)))  # key
                self.agents_extractors.append(nn.Sequential(nn.Linear(self.state_dim, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, self.n_agents)))  # agent
                self.action_extractors.append(nn.Sequential(nn.Linear(self.state_action_dim, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, adv_hypernet_embed),
                                                            nn.ReLU(),
                                                            nn.Linear(adv_hypernet_embed, self.n_agents)))  # action
            else:
                raise Exception("Error setting number of adv hypernet layers.")

    def forward(self, states, actions):
        states = states.reshape(-1, self.state_dim)
        actions = actions.reshape(-1, self.action_dim)
        data = th.cat([states, actions], dim=1)

        all_head_key = [k_ext(states) for k_ext in self.key_extractors]
        all_head_agents = [k_ext(states) for k_ext in self.agents_extractors]
        all_head_action = [sel_ext(data) for sel_ext in self.action_extractors]

        head_attend_weights = []
        for curr_head_key, curr_head_agents, curr_head_action in zip(all_head_key, all_head_agents, all_head_action):
            x_key = th.abs(curr_head_key).repeat(1, self.n_agents) + 1e-10
            x_agents = F.sigmoid(curr_head_agents)
            x_action = F.sigmoid(curr_head_action)
            weights = x_key * x_agents * x_action
            head_attend_weights.append(weights)

        head_attend = th.stack(head_attend_weights, dim=1)
        head_attend = head_attend.view(-1, self.num_kernel, self.n_agents)
        head_attend = th.sum(head_attend, dim=1)

        return head_attend


class DMAQ_SI_Weight_dropout(nn.Module):
    def __init__(self, args):
        super(DMAQ_SI_Weight, self).__init__()

        self.args = args
        self.n_agents = 1
        self.n_actions = args.n_actions
        self.state_dim = int(np.prod(args.state_shape))
        self.action_dim = args.n_agents * self.n_actions
        self.state_action_dim = self.state_dim + self.action_dim

        self.num_kernel = 2

        self.key_extractors = nn.ModuleList()
        self.agents_extractors = nn.ModuleList()
        self.action_extractors = nn.ModuleList()

        adv_hypernet_embed = self.args.adv_hypernet_embed
        for i in range(self.num_kernel):  # multi-head attention
            self.key_extractors.append(nn.Linear(self.state_dim, 1))  # key
            self.agents_extractors.append(nn.Linear(self.state_dim, self.n_agents))  # agent
            self.action_extractors.append(nn.Linear(self.state_action_dim, self.n_agents))  # action

    def forward(self, states, actions):
        states = states.reshape(-1, self.state_dim)
        actions = actions.reshape(-1, self.action_dim)
        data = th.cat([states, actions], dim=1)

        all_predictions = []

        for _ in range(num_samples):
            all_head_key = [F.dropout(k_ext(states), p=self.dropout_prob, training=self.training) for k_ext in self.key_extractors]

            # Apply dropout to agents_extractors during training
            all_head_agents = [F.dropout(k_ext(states), p=self.dropout_prob, training=self.training) for k_ext in self.agents_extractors]

            # Apply dropout to action_extractors during training
            all_head_action = [F.dropout(sel_ext(data), p=self.dropout_prob, training=self.training) for sel_ext in self.action_extractors]
           
            head_attend_weights = []
            for curr_head_key, curr_head_agents, curr_head_action in zip(all_head_key, all_head_agents, all_head_action):
                x_key = th.abs(curr_head_key).repeat(1, self.n_agents) + 1e-10
                x_agents = F.sigmoid(curr_head_agents)
                x_action = F.sigmoid(curr_head_action)
                weights = x_key * x_agents * x_action
                head_attend_weights.append(weights)

            head_attend = th.stack(head_attend_weights, dim=1)
            head_attend = head_attend.view(-1, self.num_kernel, self.n_agents)
            head_attend = th.sum(head_attend, dim=1)

            all_predictions.append(head_attend)        

        # Calculate mean and variance across Monte Carlo samples
        mean_prediction = th.mean(th.stack(all_predictions), dim=0)
        prediction_variance = th.var(th.stack(all_predictions), dim=0)

        return mean_prediction, prediction_variance
    
