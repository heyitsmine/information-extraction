# -*- coding: utf-8 -*-
########################################################
# Copyright (c) 2019, Baidu Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# imitations under the License.
########################################################
"""
This module to define neural network
"""

import json
import os
import sys
import argparse
import configparser

import paddle
import paddle.fluid as fluid

    
def db_lstm(data_reader, word, postag, p_word, conf_dict):
    """
    Neural network structure definition: Stacked bidirectional 
    LSTM network
    """
    hidden_dim = conf_dict['hidden_dim']
    depth = conf_dict['depth']
    label_dict_len = data_reader.get_dict_size('so_label_dict')
    word_emb_fixed = True if conf_dict['word_emb_fixed'] == "True" else False
    emb_distributed = not conf_dict['is_local']
    conf_dict['is_sparse'] = bool(conf_dict['is_sparse'])
    # 3 features
    word_param = fluid.ParamAttr(name=conf_dict['emb_name'],
                                 trainable=(not word_emb_fixed))
    word_embedding = fluid.layers.embedding(
        input=word,
        size=[data_reader.get_dict_size('wordemb_dict'),
            conf_dict['word_dim']],
        dtype='float32',
        is_distributed=emb_distributed,
        is_sparse=emb_distributed,
        param_attr=word_param)
    

    postag_embedding = fluid.layers.embedding(
        input=postag,
        size=[data_reader.get_dict_size('postag_dict'),
            conf_dict['postag_dim']],
        dtype='float32',
        is_distributed=emb_distributed,
        is_sparse=emb_distributed)

    
    p_embedding = fluid.layers.embedding(
        input=p_word,
        size=[data_reader.get_dict_size('wordemb_dict'),
            conf_dict['word_dim']],
        dtype='float32',
        is_distributed=emb_distributed,
        is_sparse=emb_distributed,
        param_attr=word_param)

    # embedding
    emb_layers = [word_embedding, postag_embedding, p_embedding]
    # input hidden
    hidden_0_layers = [
        fluid.layers.fc(input=emb, size=hidden_dim, act='tanh')
        for emb in emb_layers
    ]

    hidden_0 = fluid.layers.sums(input=hidden_0_layers)

    lstm_0 = fluid.layers.dynamic_lstm(
        input=hidden_0,
        size=hidden_dim,
        candidate_activation='relu',
        gate_activation='sigmoid',
        cell_activation='sigmoid')

    # stack L-LSTM and R-LSTM with direct edges
    input_tmp = [hidden_0, lstm_0]

    for i in range(1, depth):
        mix_hidden = fluid.layers.sums(input=[
            fluid.layers.fc(input=input_tmp[0], size=hidden_dim, act='tanh'),
            fluid.layers.fc(input=input_tmp[1], size=hidden_dim, act='tanh')
        ])

        lstm = fluid.layers.dynamic_lstm(
            input=mix_hidden,
            size=hidden_dim,
            candidate_activation='relu',
            gate_activation='sigmoid',
            cell_activation='sigmoid',
            is_reverse=((i % 2) == 1))

        input_tmp = [mix_hidden, lstm]
    
    # output
    feature_out = fluid.layers.sums(input=[
        fluid.layers.fc(input=input_tmp[0], size=label_dict_len, act='tanh'),
        fluid.layers.fc(input=input_tmp[1], size=label_dict_len, act='tanh')
    ])

    return feature_out
