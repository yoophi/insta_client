import os
import re
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def find_version(fname):
    '''Attempts to find the version number in the file names fname.
    Raises RuntimeError if not found.
    '''
    version = ''
    with open(fname, 'r') as fp:
        reg = re.compile(r'__version__ = [\'"]([^\'"]*)[\'"]')
        for line in fp:
            m = reg.match(line)
            if m:
                version = m.group(1)
                break
    if not version:
        raise RuntimeError('Cannot find version information')
    return version


__version__ = find_version(os.path.join("insta_client", "__init__.py"))

setup(
    name='insta_client',
    version=__version__,
    long_description=read('README.md'),
    packages=['insta_client'],
    url='http://github.com/yoophi/fluffy-id',
    license='MIT License',
    author='Pyunghyuk Yoo',
    author_email='yoophi@gmail.com',
    description='Instagram Client',
    include_package_data=True,
    zip_safe=False,
    entry_points={},
    install_requires=[
        'requests==2.11.1',
        'lxml==3.6.4',
        'instagram_text_python',
    ],
    dependency_links=[
        'git+https://github.com/yoophi/instagram-text-python.git@db05fd6106ea880beb2a800a120adee4af56c51c#egg=instagram_text_python',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)