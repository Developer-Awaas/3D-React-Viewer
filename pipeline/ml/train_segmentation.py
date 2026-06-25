"""Step 2 — train a U-Net (wall/door/window/room segmentation). GPU required.
Skeleton using segmentation_models_pytorch. Run on Colab/Kaggle."""
import glob, numpy as np, cv2, torch
from torch.utils.data import Dataset, DataLoader
import segmentation_models_pytorch as smp

NUM_CLASSES = 5
class PlanDS(Dataset):
    def __init__(self, root, size=512):
        self.imgs=sorted(glob.glob(f"{root}/img_*.png")); self.size=size
    def __len__(self): return len(self.imgs)
    def __getitem__(self,i):
        img=cv2.resize(cv2.imread(self.imgs[i]),(self.size,self.size))/255.
        msk=cv2.resize(cv2.imread(self.imgs[i].replace("img_","msk_"),0),(self.size,self.size),interpolation=cv2.INTER_NEAREST)
        return torch.tensor(img).permute(2,0,1).float(), torch.tensor(msk).long()

def train(root, epochs=30):
    dev="cuda" if torch.cuda.is_available() else "cpu"
    net=smp.Unet("resnet34", classes=NUM_CLASSES, in_channels=3).to(dev)
    dl=DataLoader(PlanDS(root), batch_size=8, shuffle=True)
    opt=torch.optim.Adam(net.parameters(),1e-3); lossf=torch.nn.CrossEntropyLoss()
    for ep in range(epochs):
        for x,y in dl:
            x,y=x.to(dev),y.to(dev); opt.zero_grad()
            loss=lossf(net(x),y); loss.backward(); opt.step()
        print(f"epoch {ep} loss {loss.item():.3f}")
    torch.onnx.export(net, torch.randn(1,3,512,512).to(dev), "plan_unet.onnx",
                      input_names=["img"], output_names=["mask"])
    print("exported plan_unet.onnx  (use with infer_to_schema.py)")

if __name__ == "__main__":
    import sys; train(sys.argv[1])
