"""
Tests for snpeff_util.py
"""

"""
Tests for alignment_pipeline.py
"""

import os

from django.test import TestCase
from django.test.utils import override_settings
import vcf

from main.models import AlignmentGroup
from main.models import clean_filesystem_location
from main.models import Dataset
from main.models import ExperimentSample
from main.models import ExperimentSampleToAlignment
from main.models import get_dataset_with_type
from main.models import Project
from main.models import User
from main.models import Variant
from scripts.snpeff_util import build_snpeff
from scripts.snpeff_util import run_snpeff
from scripts.snpeff_util import get_snpeff_config_path
from scripts.snp_callers import run_snp_calling_pipeline
from scripts.snp_callers import VCF_DATASET_TYPE
from scripts.snp_callers import VCF_ANNOTATED_DATASET_TYPE
from scripts.import_util import add_dataset_to_entity
from scripts.import_util import copy_and_add_dataset_source
from scripts.import_util import copy_dataset_to_entity_data_dir
from scripts.import_util import import_reference_genome_from_local_file
from settings import PWD as GD_ROOT


TEST_DIR = os.path.join(GD_ROOT, 'test_data', 'genbank_aligned')

TEST_GENBANK = os.path.join(TEST_DIR, 'mg1655_tolC_through_zupT.gb')

TEST_UNANNOTATED_VCF = os.path.join(TEST_DIR, 'bwa_align_unannotated.vcf')

class TestSnpeff(TestCase):

    def setUp(self):
        user = User.objects.create_user('test_username', password='password',
                email='test@example.com')

        # Grab a project.
        self.project = Project.objects.create(title='snpeff test project',
                owner=user.get_profile())

        # Create a ref genome.
        self.reference_genome = import_reference_genome_from_local_file(
                self.project, 'snpeff test ref genome', TEST_GENBANK, 'genbank')

        # Create a new alignment group.
        self.alignment_group = AlignmentGroup.objects.create(
                label='test alignment', reference_genome=self.reference_genome)

        # Create a sample.
        self.sample_1 = ExperimentSample.objects.create(
                project=self.project,
                label='test sample 1')

        # Create relationship between alignment and sample.
        self.sample_alignment = ExperimentSampleToAlignment.objects.create(
                alignment_group=self.alignment_group,
                experiment_sample=self.sample_1)

        # Add unannotated SNP data.
        self.vcf_dataset = Dataset.objects.create(
                type=VCF_DATASET_TYPE,
                label=VCF_DATASET_TYPE,
                filesystem_location=TEST_UNANNOTATED_VCF)
        self.alignment_group.dataset_set.add(self.vcf_dataset)

    def test_build_snpeff(self):
        """ Run the config pipeline and check that all the required files,
            the reference genome config file and the snpeff database file,
            are present.
        """
        build_snpeff(self.reference_genome)
        snpeff_path = get_snpeff_config_path(self.reference_genome)
        snpeff_config_file = os.path.join(snpeff_path, 'snpeff.config')
        snpeff_database_file = os.path.join(snpeff_path,self.reference_genome.uid,
            'snpEffectPredictor.bin')

        self.assertTrue(os.path.exists(snpeff_config_file),
                    msg= 'SnpEff config file was not found.')
        self.assertTrue(os.path.exists(snpeff_database_file),
                    msg= 'SnpEff annotation database was not found.')

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS = True,
        CELERY_ALWAYS_EAGER = True, BROKER_BACKEND = 'memory')
    def test_run_snpeff(self):
        """Test running the pipeline that annotates SNPS.

        This test doesn't check the accuracy of the SNP-annotation. The test is
        intended just to run the pipeline and make sure there are no errors.
        """

        # Try running snpeff
        run_snpeff(self.alignment_group, Dataset.TYPE.BWA_ALIGN)

        # Check that the alignment group has a freebayes vcf dataset associated
        # with it.
        vcf_dataset = get_dataset_with_type(self.alignment_group,
                VCF_ANNOTATED_DATASET_TYPE)
        self.assertIsNotNone(vcf_dataset,
            'SnpEff annotated vcf dataset was not found after running snpeff.')

        # Make sure the .vcf file actually exists.
        self.assertTrue(os.path.exists(vcf_dataset.get_absolute_location()),
            'SnpEff annotated vcf file was not found after running snpeff.')

        # Make sure the vcf is valid by reading it using pyvcf.
        with open(vcf_dataset.get_absolute_location()) as vcf_fh:
            try:
                reader = vcf.Reader(vcf_fh)
                record = reader.next()
            except:
                self.fail("Not valid vcf")
            assert 'EFF' in record.INFO, (
                    'No EFF INFO field found in snpeff VCF file.')

