#!/usr/bin/env python2.7
# Copyright 2016 Arjun Arkal Rao
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function
from math import ceil

from protect.common import (docker_call,
                            docker_path,
                            export_results,
                            get_files_from_filestore,
                            untargz)
from toil.job import PromisedRequirement

import os


# disk for rsem
def rsem_disk(star_bams, rsem_index):
    star_transcriptome_bam = star_bams['rna_transcriptome.bam']
    return int(3 * ceil(star_transcriptome_bam.size + 524288) +
               4 * ceil(rsem_index.size + 524288))


def wrap_rsem(job, star_bams, univ_options, rsem_options):
    """
    A wrapper for run_rsem using the results from run_star as input.

    :param dict star_bams: dict of results from star
    :param dict univ_options: Dict of universal options used by almost all tools
    :param dict rsem_options: Options specific to rsem
    :return: Dict of gene- and isoform-level expression calls
             output_files:
                 |- 'rsem.genes.results': fsID
                 +- 'rsem.isoforms.results': fsID
    :rtype: dict
    """
    rsem = job.addChildJobFn(run_rsem, star_bams['rna_transcriptome.bam'],
                             univ_options, rsem_options, cores=rsem_options['n'],
                             disk=PromisedRequirement(rsem_disk, star_bams,
                                                      rsem_options['index']))

    return rsem.rv()


def run_rsem(job, rna_bam, univ_options, rsem_options):
    """
    Run rsem on the input RNA bam.

    ARGUMENTS
    :param toil.fileStore.FileID rna_bam: fsID of a transcriptome bam generated by STAR
    :param dict univ_options: Dict of universal options used by almost all tools
    :param dict rsem_options: Options specific to rsem
    :return: Dict of gene- and isoform-level expression calls
             output_files:
                 |- 'rsem.genes.results': fsID
                 +- 'rsem.isoforms.results': fsID
    :rtype: dict
    """
    work_dir = os.getcwd()
    input_files = {
        'star_transcriptome.bam': rna_bam,
        'rsem_index.tar.gz': rsem_options['index']}
    input_files = get_files_from_filestore(job, input_files, work_dir, docker=False)

    input_files['rsem_index'] = untargz(input_files['rsem_index.tar.gz'], work_dir)
    input_files = {key: docker_path(path) for key, path in input_files.items()}

    parameters = ['--paired-end',
                  '-p', str(rsem_options['n']),
                  '--bam',
                  input_files['star_transcriptome.bam'],
                  '--no-bam-output',
                  '/'.join([input_files['rsem_index'], univ_options['ref']]),
                  'rsem']
    docker_call(tool='rsem', tool_parameters=parameters, work_dir=work_dir,
                dockerhub=univ_options['dockerhub'], tool_version=rsem_options['version'])
    output_files = {}
    for filename in ('rsem.genes.results', 'rsem.isoforms.results'):
        output_files[filename] = job.fileStore.writeGlobalFile('/'.join([work_dir, filename]))
        export_results(job, output_files[filename], '/'.join([work_dir, filename]), univ_options,
                       subfolder='expression')
    job.fileStore.logToMaster('Ran rsem on %s successfully' % univ_options['patient'])
    return output_files
