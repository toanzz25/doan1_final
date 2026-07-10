# HP 8903B Pro Automation System

Ung dung dieu khien va tu dong hoa qua trinh do voi may phan tich am thanh HP 8903B. Phan mem duoc viet bang Python, su dung giao dien CustomTkinter, dieu khien thiet bi qua PyVISA/GPIB va hien thi ket qua do tren do thi Matplotlib theo thang tan so logarit.

Du an nay duoc xay dung cho do an do luong tu dong, voi muc tieu giam thao tac thu cong tren thiet bi HP 8903B, tu dong quet tan so, ghi nhan du lieu, hien thi do thi va xuat ket qua ra file.

## Chuc nang chinh

- Ket noi may HP 8903B qua dia chi VISA/GPIB, mac dinh `GPIB0::28::INSTR`.
- Do stepped sweep theo dai tan nguoi dung nhap, tu 20 Hz den 100 kHz.
- Ho tro nhieu che do do cua HP 8903B:
  - AC LEVEL - `M1`
  - DC LEVEL - `S1`
  - SINAD - `M2`
  - SIG/NOISE - `S2`
  - DISTN / THD+N - `M3`
  - DISTN LEVEL - `S3`
- Tuy chon Ratio `R0/R1`.
- Tuy chon don vi hien thi: `%`, `dB`, `V`, `mV`, `dBm` tuy theo che do do.
- Cau hinh bo loc HP/BP va LP:
  - HP/BP Off `H0`
  - Left Plug-in `H1`
  - Right Plug-in `H2`
  - LP Off `L0`
  - 30 kHz LP `L1`
  - 80 kHz LP `L2`
- Cau hinh nang cao:
  - Tro khang ngo ra 600 ohm hoac 50 ohm
  - Dai do input
  - Detector Fast/Slow RMS
  - Gain Auto, 0 dB, 20 dB
- Chay 1 den 5 luot quet va ve tung duong tren cung mot do thi.
- Hien thi gia tri tan so va gia tri do theo thoi gian thuc.
- Tu dong can truc do thi theo du lieu do.
- Ho tro zoom, pan, cursor snap va crosshair tren do thi.
- Xuat du lieu do ra CSV, co cot trung binh khi do nhieu luot.
- Xuat anh do thi PNG hoac copy anh vao clipboard neu may co thu vien phu hop.

## Cau truc file

```text
.
|-- main.py              # Diem chay chuong trinh
|-- gui.py               # Giao dien, do thi, nut dieu khien, export
|-- driver.py            # Ket noi PyVISA va tao lenh dieu khien HP 8903B
|-- sweep.py             # Logic quet tan so stepped sweep
|-- HP8903B_V6 (1).py    # File nguon ban dau / ban tham chieu
```

## Yeu cau he thong

- Windows.
- Python 3.10 tro len.
- May do HP 8903B.
- Card/chuyen doi GPIB hoac giao tiep VISA tuong thich.
- Driver VISA da cai dat, vi du NI-VISA hoac Keysight VISA.
- Dia chi thiet bi dung voi cau hinh he thong, vi du `GPIB0::28::INSTR`.

## Thu vien Python can cai

```powershell
pip install customtkinter matplotlib numpy pyvisa
```

Neu muon dung chuc nang copy anh do thi vao clipboard, cai them:

```powershell
pip install pillow pywin32
```

## Cach chay chuong trinh

Tai thu muc du an, chay:

```powershell
python main.py
```

File `main.py` se khoi tao lop `HP8903B_App` trong `gui.py` va mo giao dien chinh.

## Huong dan su dung nhanh

1. Ket noi HP 8903B voi may tinh qua GPIB/VISA.
2. Mo ung dung bang `python main.py`.
3. Nhap dia chi thiet bi, mac dinh la `GPIB0::28::INSTR`.
4. Bam `KET NOI`.
5. Chon che do do: AC, DC, SINAD, SIG/NOISE, DISTN hoac DISTN LEVEL.
6. Nhap tan so bat dau, tan so ket thuc, bien do nguon phat va so diem quet.
7. Chon bo loc, tro khang, dai do, detector, gain neu can.
8. Chon so luot quet.
9. Bam `START` de bat dau do.
10. Bam `STOP` neu can dung qua trinh do.
11. Sau khi co du lieu, co the xuat CSV hoac anh do thi.

## Dinh dang du lieu nhap

Tan so:

- `20`
- `1000`
- `1k`
- `20 kHz`

Bien do:

- `1`
- `1.5 V`
- `500 mV`

So diem quet:

- Tu 2 den 255 diem.

## Gioi han an toan trong phan mem

Phan mem co kiem tra gioi han truoc khi gui lenh xuong thiet bi:

- Tan so: 20 Hz den 100 kHz.
- Bien do nguon phat: lon hon 0 va khong vuot qua 6 V.
- Bien do dang mV: khong vuot qua 6000 mV.
- So diem quet: 2 den 255 diem.

## Nguyen ly hoat dong

Khi bat dau do, chuong trinh tao mang tan so theo thang logarit bang `numpy.logspace`. Voi moi diem tan so, phan mem:

1. Gui lenh dat tan so `FR...HZ` hoac `FR...KZ`.
2. Cho thiet bi on dinh trong thoi gian ngan.
3. Gui lenh trigger `T3`.
4. Doc gia tri tra ve tu HP 8903B.
5. Luu tan so va gia tri do vao mang du lieu.
6. Cap nhat do thi tren giao dien.

Neu chon nhieu luot quet, moi luot se duoc ve thanh mot duong rieng tren do thi. Khi xuat CSV, chuong trinh tao cot rieng cho tung luot va them cot trung binh neu co tu hai luot tro len.

## Cac lenh HP 8903B duoc su dung

Mot so lenh chinh trong chuong trinh:

- `AU`: Auto range.
- `M1`: AC Level.
- `S1`: DC Level.
- `M2`: SINAD.
- `S2`: Signal to Noise.
- `M3`: Distortion / THD+N.
- `S3`: Distortion Level.
- `R0`, `R1`: Tat/bat Ratio.
- `LN`, `LG`: Chon dang hien thi linear/log.
- `FR...HZ`, `FR...KZ`: Dat tan so.
- `AP ... VL`, `AP ... MV`: Dat bien do nguon phat.
- `T3`: Trigger mot lan do va doc ket qua.
- `T0`: Dung trigger/sweep.

## Xuat du lieu

CSV gom cac cot:

- `Frequency (Hz)`
- `Sweep 1`
- `Sweep 2`, `Sweep 3`, ... neu do nhieu luot
- `Average` neu co nhieu hon mot luot

Anh do thi co the luu dang PNG voi do phan giai cao de chen vao bao cao.

## Loi thuong gap

Khong ket noi duoc thiet bi:

- Kiem tra dia chi GPIB/VISA.
- Kiem tra HP 8903B da bat nguon va day GPIB da ket noi.
- Kiem tra NI-VISA/Keysight VISA da nhan thiet bi.
- Thu dung cong cu VISA Interactive Control de test dia chi truoc.

Khong doc duoc gia tri do:

- Kiem tra che do do co phu hop voi tin hieu dau vao.
- Kiem tra bien do nguon phat va dai do.
- Tang thoi gian cho on dinh neu thiet bi phan hoi cham.

Do thi khong hien du lieu:

- Kiem tra da bam `START` sau khi ket noi.
- Kiem tra so diem quet nam trong khoang 2 den 255.
- Kiem tra thiet bi co tra ve gia tri so hop le hay khong.

## Ghi chu phat trien

Ban dau toan bo chuong trinh nam trong `HP8903B_V6 (1).py`. Hien tai code duoc tach thanh cac module nho hon de de quan ly:

- Logic giao dien nam trong `gui.py`.
- Logic giao tiep thiet bi nam trong `driver.py`.
- Logic stepped sweep nam trong `sweep.py`.
- Diem chay chuong trinh nam trong `main.py`.

Khi can doi lenh thiet bi, uu tien sua trong `driver.py`. Khi can doi cach quet tan so hoac cach xu ly du lieu do, uu tien sua trong `sweep.py`. Khi can doi giao dien, nut bam, do thi hoac export, uu tien sua trong `gui.py`.
