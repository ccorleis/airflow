#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from unittest import mock

import pytest

from airflow.api.common.trigger_dag import _trigger_dag
from airflow.exceptions import AirflowException
from airflow.models.dag import DAG
from airflow.models.dagrun import DagRun
from airflow.utils import timezone
from tests.test_utils import db

pytestmark = [pytest.mark.db_test, pytest.mark.skip_if_database_isolation_mode]


class TestTriggerDag:
    def setup_method(self) -> None:
        db.clear_db_runs()

    def teardown_method(self) -> None:
        db.clear_db_runs()

    @mock.patch("airflow.models.DagBag")
    def test_trigger_dag_dag_not_found(self, dag_bag_mock):
        dag_bag_mock.dags = {}
        with pytest.raises(AirflowException):
            _trigger_dag("dag_not_found", dag_bag_mock)

    @mock.patch("airflow.api.common.trigger_dag.DagRun", spec=DagRun)
    @mock.patch("airflow.models.DagBag")
    def test_trigger_dag_dag_run_exist(self, dag_bag_mock, dag_run_mock):
        dag_id = "dag_run_exist"
        dag = DAG(dag_id, schedule=None)
        dag_bag_mock.dags = [dag_id]
        dag_bag_mock.get_dag.return_value = dag
        dag_run_mock.find_duplicate.return_value = DagRun()
        with pytest.raises(AirflowException):
            _trigger_dag(dag_id, dag_bag_mock)

    @mock.patch("airflow.models.DagBag")
    def test_trigger_dag_with_too_early_start_date(self, dag_bag_mock):
        dag_id = "trigger_dag_with_too_early_start_date"
        dag = DAG(
            dag_id=dag_id,
            schedule=None,
            default_args={"start_date": timezone.datetime(2016, 9, 5, 10, 10, 0)},
        )
        dag_bag_mock.dags = [dag_id]
        dag_bag_mock.get_dag.return_value = dag

        with pytest.raises(ValueError):
            _trigger_dag(dag_id, dag_bag_mock, execution_date=timezone.datetime(2015, 7, 5, 10, 10, 0))

    @mock.patch("airflow.models.DagBag")
    def test_trigger_dag_with_valid_start_date(self, dag_bag_mock):
        dag_id = "trigger_dag_with_valid_start_date"
        dag = DAG(
            dag_id=dag_id,
            schedule=None,
            default_args={"start_date": timezone.datetime(2016, 9, 5, 10, 10, 0)},
        )
        dag_bag_mock.dags = [dag_id]
        dag_bag_mock.get_dag.return_value = dag
        dag_bag_mock.dags_hash = {}

        dagrun = _trigger_dag(dag_id, dag_bag_mock, execution_date=timezone.datetime(2018, 7, 5, 10, 10, 0))

        assert dagrun

    @pytest.mark.parametrize(
        "conf, expected_conf",
        [
            (None, {}),
            ({"foo": "bar"}, {"foo": "bar"}),
            ('{"foo": "bar"}', {"foo": "bar"}),
        ],
    )
    @mock.patch("airflow.models.DagBag")
    def test_trigger_dag_with_conf(self, dag_bag_mock, conf, expected_conf):
        dag_id = "trigger_dag_with_conf"
        dag = DAG(dag_id, schedule=None)
        dag_bag_mock.dags = [dag_id]
        dag_bag_mock.get_dag.return_value = dag

        dag_bag_mock.dags_hash = {}

        dagrun = _trigger_dag(dag_id, dag_bag_mock, conf=conf)

        assert dagrun.conf == expected_conf
