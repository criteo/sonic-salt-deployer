# docker build . -t deployer-build
# docker run --rm -v "$(pwd):/opt/build-pex/" deployer-builder
FROM centos:8

RUN yum update -y
RUN dnf group install -y "Development Tools"
RUN yum install -y python3 python3-pip gcc python3-devel openssl openssl-devel libffi-devel
RUN /usr/bin/pip3 install pip --upgrade
RUN /usr/bin/pip3 install tox==3.14.2
RUN /usr/bin/pip3 install six==1.10.0
RUN /usr/bin/pip3 install virtualenv==16.7.9

RUN mkdir /opt/build -p
WORKDIR /opt/build

CMD [ "/usr/local/bin/tox", "-e", "bundle" ]
